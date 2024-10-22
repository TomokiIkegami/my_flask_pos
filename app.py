from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# SQLite データベースの設定
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'sales.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 売り上げ情報のモデル
class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Integer, nullable = False)
    quantity = db.Column(db.Integer, nullable = False)
    total = db.Column(db.Integer, nullable = False)

# データベースの初期化
@app.before_request
def create_tables():
    db.create_all()

# 商品データ
items = [
    {"id": 1, "name": "白玉団子（黒蜜きなこ）", "price": 200},
    {"id": 2, "name": "白玉団子（みたらし）", "price": 200},
    {"id": 3, "name": "白玉団子（あんこ）", "price": 200},
]

@app.route('/', methods=['GET', 'POST'])
def index():
    total = 0
    selected_item = None
    quantity = 1    # デフォルトの数量
    if request.method == 'POST':
        item_id = int(request.form['item'])
        quantity = int(request.form['quantity'])
        selected_item = next(item for item in items if item['id'] == item_id)
        total = selected_item['price'] * quantity

        # 売り上げデータをデータベースに記録
        sale = Sale(
            item_name = selected_item['name'],
            price = selected_item['price'],
            quantity = quantity,
            total = total
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
    return render_template('sales.html', sales_records = sales_records, total_sales = total_sales)

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    # IDで特定の売上データを検索
    sale_to_delete = Sale.query.get_or_404(id)

    try:
        # データベースから削除
        db.session.delete(sale_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return f'削除に失敗しました:{str(e)}'


if __name__ == '__main__':
    app.run(debug=True)