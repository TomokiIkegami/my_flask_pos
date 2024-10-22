from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime  # datetime モジュールをインポート
import os

app = Flask(__name__)

# SQLite データベースの設定
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'sales.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 商品データをデータベースに初期化する関数を作成
def init_items():
    item_data = [
        {"name": "白玉団子（黒蜜きなこ）", "price": 200},
        {"name": "白玉団子（みたらし）", "price": 200},
        {"name": "白玉団子（あんこ）", "price": 200},
    ]
    for item in item_data:
        new_item = Item(name=item["name"], price=item["price"])
        db.session.add(new_item)
    db.session.commit()

# データベースの初期化
@app.before_request
def create_tables():
    db.create_all()
    # 商品がまだ存在しない場合には初期商品を追加
    if Item.query.count() == 0:
        init_items()


@app.route('/', methods=['GET', 'POST'])
def index():
    total = 0
    selected_item = None
    quantity = 1    # デフォルトの数量

    # データベースから商品データを取得
    items = Item.query.all()

    if request.method == 'POST':
        item_id = int(request.form['item'])
        quantity = int(request.form['quantity'])
        selected_item = Item.query.get(item_id)  # 選択された商品の詳細を取得
        total = selected_item.price * quantity

        # 売り上げデータをデータベースに記録
        sale = Sale(
            item_name=selected_item.name,
            price=selected_item.price,
            quantity=quantity,
            total=total
        )
        db.session.add(sale)
        db.session.commit()

        return redirect(url_for('sales'))

    return render_template('index.html', items=items, total=total, quantity=quantity, selected_item=selected_item)

@app.route('/sales')
def sales():
    # データベースから全ての売上履歴を取得
    sales_records = Sale.query.all()
    total_sales = sum(record.total for record in sales_records)
    return render_template('sales.html', sales_records=sales_records, total_sales=total_sales)

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    # IDで特定の売上データを検索
    sale_to_delete = Sale.query.get_or_404(id)

    try:
        # データベースから削除
        db.session.delete(sale_to_delete)
        db.session.commit()
        return redirect('/')
    except Exception as e:
        return f'削除に失敗しました:{str(e)}'

@app.route('/edit_item/<int:id>', methods=['GET', 'POST'])
def edit_item(id):
    item_to_edit = Item.query.get_or_404(id)

    if request.method == 'POST':
        item_to_edit.name = request.form['item_name']
        item_to_edit.price = int(request.form['price'])
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('edit_item.html', item=item_to_edit)

@app.route('/items', methods=['GET'])
def items():
    # データベースからすべてのアイテムを取得
    all_items = Item.query.all()
    return render_template('items.html', items=all_items)

# 商品の追加ルート
@app.route('/add_item', methods=['GET', 'POST'])
def add_item():
    if request.method == 'POST':
        # フォームからデータを取得
        item_name = request.form['name']
        item_price = int(request.form['price'])

        # データベースに追加
        new_item = Item(name=item_name, price=item_price)
        db.session.add(new_item)
        db.session.commit()
        
        return redirect(url_for('items'))

    return render_template('add_item.html')

# 商品の削除ルート
@app.route('/delete_item/<int:id>', methods=['POST'])
def delete_item(id):
    item_to_delete = Item.query.get_or_404(id)

    try:
        db.session.delete(item_to_delete)
        db.session.commit()
        return redirect(url_for('items'))
    except Exception as e:
        return f'削除に失敗しました: {str(e)}'


if __name__ == '__main__':
    app.run(debug=True)
