from flask import Flask, render_template, request, redirect, url_for, flash, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired
import os
import csv
import io
from datetime import datetime, timedelta

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get('SECRET_KEY', 'default-secret-key')

# SQLite データベースの設定
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'sales.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Flask-login の設定
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ユーザーモデル
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(120), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def init_admin_user():
    # 環境変数から取得
    admin_username = os.environ.get('ADMIN_USERNAME')
    admin_password = os.environ.get('ADMIN_PASSWORD')

    if not admin_username or not admin_password:
        raise ValueError("環境変数 'ADMIN_USERNAME' および 'ADMIN_PASSWORD' を設定してください。")

    # すでに管理者ユーザーが存在しない場合にのみ追加
    if not User.query.filter_by(username=admin_username).first():
        admin = User(username=admin_username)
        admin.set_password(admin_password)  # ハッシュ化してパスワードを設定
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user '{admin_username}' added.")

# 商品情報のモデル
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Integer, nullable=False)

# 売り上げ情報のモデル
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    shift_number = db.Column(db.Integer, nullable=True)  # シフト番号を追加
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=9))  # JST に変更

    def __repr__(self):
        return f'<Sale {self.item_name}, {self.total}>'

# 商品データをデータベースに初期化する関数
def init_items():
    item_data = [
        {"name": "前売券", "price": 1000},
        {"name": "茶席券（緑色）", "price": 1000},
        {"name": "当日券", "price": 1500},
    ]
    for item in item_data:
        if not Item.query.filter_by(name=item["name"]).first():
            new_item = Item(name=item["name"], price=item["price"])
            db.session.add(new_item)
    db.session.commit()

# データベースの初期化
@app.before_request
def setup_database():
    db.create_all()
    # init_items()
    init_admin_user()

# ログインフォーム
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

# ログインルート
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # ユーザーが存在するか確認
        user = User.query.filter_by(username=username).first()
        
        # デバッグメッセージを追加
        if user:
            print(f"User '{username}' found.")
        else:
            print(f"User '{username}' not found.")

        # パスワードが一致するか確認
        if user and user.check_password(password):
            print("Password matched!")  # パスワードが一致した場合のデバッグメッセージ
            login_user(user)
            return redirect(url_for('index'))
        else:
            print("Password did not match or user not found.")  # 一致しなかった場合のデバッグメッセージ
            flash('Invalid username or password', 'danger')  # ログイン失敗メッセージ

    return render_template('login.html')


# ログアウトルート
@app.route('/logout')
# @login_required
def logout():
    logout_user()
    flash('ログアウトしました', 'info')
    return redirect(url_for('login'))

# メインページのルート
@app.route('/', methods=['GET', 'POST'])
# @login_required
def index():
    items = Item.query.all()
    total = 0
    sales_records = []
    message = None  # 初期化

    # 商品が登録されていない場合のメッセージを設定
    if not items:
        message = "「商品一覧」ページから商品を登録してください"

    if request.method == 'POST' and items:
        shift_number = request.form.get('shift_number', None)
        shift_number = int(shift_number) if shift_number else None
        quantities = request.form.getlist('quantities[]')
        for item in items:
            quantity = request.form.get(f'quantities[{item.id}]', 0)
            quantity = int(quantity)
            if quantity > 0:
                total += item.price * quantity
                new_sale = Sale(item_name=item.name, price=item.price, quantity=quantity, total=item.price * quantity, shift_number=shift_number)
                db.session.add(new_sale)
                sales_records.append({'item_name': item.name, 'price': item.price, 'quantity': quantity, 'total': item.price * quantity, 'shift_number': shift_number})
        db.session.commit()

    return render_template('index.html', items=items, total=total, sales_records=sales_records, message=message)

# 売上履歴のルート
@app.route('/sales', methods=['GET', 'POST'])
# @login_required
def sales():
    items = Item.query.all()
    total_sales = 0
    sales_records = []

    if request.method == 'POST':
        quantities = request.form.getlist('quantities[]')
        for item in items:
            quantity = request.form.get(f'quantities[{item.id}]', 0)
            quantity = int(quantity)
            if quantity > 0:
                total = item.price * quantity
                total_sales += total
                new_sale = Sale(item_name=item.name, price=item.price, quantity=quantity, total=total)
                db.session.add(new_sale)
                sales_records.append(new_sale)

        db.session.commit()

    # 作成日時で昇順にソートして売上データを取得
    sales_records = Sale.query.order_by(Sale.created_at.desc()).all()
    total_sales = sum(record.total for record in sales_records)
    return render_template('sales.html', items=items, total_sales=total_sales, sales_records=sales_records)

# 売上履歴の削除ルート
@app.route('/delete/<int:id>', methods=['POST'])
# @login_required
def delete(id):
    sale_to_delete = Sale.query.get_or_404(id)
    try:
        db.session.delete(sale_to_delete)
        db.session.commit()
        return redirect('/sales')
    except Exception as e:
        return f'削除に失敗しました: {str(e)}'

# 商品情報編集のルート
@app.route('/edit_item/<int:id>', methods=['GET', 'POST'])
# @login_required
def edit_item(id):
    item_to_edit = Item.query.get_or_404(id)

    if request.method == 'POST':
        item_to_edit.name = request.form['item_name']
        item_to_edit.price = int(request.form['price'])
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('edit_item.html', item=item_to_edit)

# 商品一覧のルート
@app.route('/items', methods=['GET'])
# @login_required
def items():
    all_items = Item.query.all()
    return render_template('items.html', items=all_items)

# 商品追加のルート
@app.route('/add_item', methods=['GET', 'POST'])
# @login_required
def add_item():
    if request.method == 'POST':
        item_name = request.form['name']
        item_price = int(request.form['price'])

        new_item = Item(name=item_name, price=item_price)
        db.session.add(new_item)
        db.session.commit()
        
        return redirect(url_for('items'))

    return render_template('add_item.html')

# 商品削除のルート
@app.route('/delete_item/<int:id>', methods=['POST'])
# @login_required
def delete_item(id):
    item_to_delete = Item.query.get_or_404(id)
    try:
        db.session.delete(item_to_delete)
        db.session.commit()
        return redirect(url_for('items'))
    except Exception as e:
        return f'削除に失敗しました: {str(e)}'

# 売上ダッシュボードの√
@app.route('/dashboard')
def dashboard():
    from collections import defaultdict

    shift_summary = defaultdict(lambda: {'quantity': 0, 'total': 0})
    shift_product_summary = defaultdict(lambda: defaultdict(int))  # ← 追加

    # 合計売上個数、売上額、直近1時間の売上額
    total_quantity = db.session.query(db.func.sum(Sale.quantity)).scalar() or 0
    total_sales = db.session.query(db.func.sum(Sale.total)).scalar() or 0

    # JST に直近1時間の時間を取得
    one_hour_ago = datetime.utcnow() + timedelta(hours=9) - timedelta(hours=1)
    sales_last_hour = db.session.query(db.func.sum(Sale.total)).filter(Sale.created_at >= one_hour_ago).scalar() or 0

    # 売上データの取得
    sales = Sale.query.all()

    hourly_sales = {}
    product_sales = {}

    for sale in sales:
        # シフトごとの合計
        if sale.shift_number is not None:
            shift_summary[sale.shift_number]['quantity'] += sale.quantity
            shift_summary[sale.shift_number]['total'] += sale.total

            # ★ シフト × 商品 の売上数を加算
            shift_product_summary[sale.shift_number][sale.item_name] += sale.quantity

        # JSTに変換して時間ごとの売上集計
        hour = (sale.created_at).strftime('%m/%d %H:00')
        if hour not in hourly_sales:
            hourly_sales[hour] = 0
        hourly_sales[hour] += sale.quantity

        # 商品ごとの売上（円グラフ用）
        if sale.item_name not in product_sales:
            product_sales[sale.item_name] = 0
        product_sales[sale.item_name] += sale.quantity

    # 時間順に並べ替え
    sorted_hours = sorted(hourly_sales.keys())
    quantities = [hourly_sales.get(hour, 0) for hour in sorted_hours]

    # 累計売上個数の計算
    cumulative_quantities = []
    cumulative_sum = 0
    for q in quantities:
        cumulative_sum += q
        cumulative_quantities.append(cumulative_sum)

    # 商品名と売上数量（円グラフ用）
    product_names = list(product_sales.keys())
    product_quantities = list(product_sales.values())

    return render_template(
        'dashboard.html',
        total_quantity=total_quantity,
        total_sales=total_sales,
        sales_last_hour=sales_last_hour,
        sales=sales,
        sorted_hours=sorted_hours,
        quantities=quantities,
        cumulative_quantities=cumulative_quantities,
        product_names=product_names,
        product_quantities=product_quantities,
        shift_summary=shift_summary,
        product_sales=product_sales,
        shift_product_summary=shift_product_summary,  # ← 新しく追加
    )


# 売上データのCSVダウンロード用のルート
@app.route('/download_csv')
def download_csv():
    # 売上データの取得（sales_records など）
    sales_records = Sale.query.all() # 既存の関数または処理で売上データを取得

    # CSVをメモリ上で生成
    output = io.StringIO()
    writer = csv.writer(output)
    # CSVのヘッダー行
    writer.writerow(['商品名', '単価', '数量', '合計金額', '日時'])
    
    # CSVのデータ行
    for record in sales_records:
        writer.writerow([
            record.item_name,
            record.price,
            record.quantity,
            record.total,
            record.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # ポインタを先頭に戻す
    output.seek(0)
    
    # CSVをダウンロード用にレスポンス
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='sales_records.csv'
    )

# クローラー対策用ファイルへのアクセス用ルート
@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

if __name__ == '__main__':
    app.run(debug=False)
