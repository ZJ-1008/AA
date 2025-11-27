from flask import Flask, render_template, request, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import uuid
import qrcode

# ----------------- 基础配置 -----------------
app = Flask(__name__)

# 使用当前目录下的 SQLite 数据库 trace.db
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trace.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ----------------- 数据模型 -----------------
class ProductTrace(db.Model):
    """产品追溯信息表"""
    id = db.Column(db.Integer, primary_key=True)
    trace_id = db.Column(db.String(50), unique=True, nullable=False)   # 追溯码
    product_name = db.Column(db.String(100), nullable=False)           # 产品名称
    model = db.Column(db.String(100))                                  # 型号
    material = db.Column(db.String(200))                               # 材料
    material_origin = db.Column(db.String(200))                        # 材料产地
    material_batch = db.Column(db.String(100))                         # 材料批次
    standard_code = db.Column(db.String(200))                          # 执行标准
    function_desc = db.Column(db.Text)                                 # 功能描述
    key_params = db.Column(db.Text)                                    # 关键参数（可以写成JSON文本）
    prod_batch = db.Column(db.String(100))                             # 生产批次
    prod_date = db.Column(db.String(20))                               # 生产日期（简单用字符串）
    prod_line = db.Column(db.String(50))                               # 产线/工厂
    qc_result = db.Column(db.String(50))                               # 质检结果
    qc_person = db.Column(db.String(50))                               # 检验员
    warranty_months = db.Column(db.Integer)                            # 质保（月）
    qr_image_path = db.Column(db.String(255))                          # 二维码图片相对路径
    created_at = db.Column(db.DateTime, default=datetime.utcnow)       # 创建时间
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)                   # 更新时间


class ScanLog(db.Model):
    """扫码记录表"""
    id = db.Column(db.Integer, primary_key=True)
    trace_id = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow)


# 在应用上下文中创建所有表（兼容 Flask 3）
with app.app_context():
    db.create_all()


# ----------------- 工具函数 -----------------
def generate_trace_id():
    """
    生成一个简单的追溯码：
    P + 日期(YYYYMMDD) + 6位随机
    例如：P20251126A1B2C3
    """
    date_str = datetime.now().strftime("%Y%m%d")
    rand = uuid.uuid4().hex[:6].upper()
    return f"P{date_str}{rand}"


def generate_qr(trace_id):
    """
    为追溯码生成二维码图片，并返回相对路径
    """
    # 使用 GitHub Pages 网址，替换为实际的域名
    base_url = "https://zj-1008.github.io/trace-system/trace_page.html?trace_id="
    url = base_url + trace_id

    save_dir = os.path.join("static", "qrcodes")
    os.makedirs(save_dir, exist_ok=True)

    file_path = os.path.join(save_dir, f"{trace_id}.png")
    img = qrcode.make(url)
    img.save(file_path)

    # 返回相对路径，模板里用 / + 这个路径访问
    return file_path


# ----------------- 管理后台路由 -----------------
@app.route("/admin/products")
def admin_products():
    """
    产品追溯信息列表
    """
    products = ProductTrace.query.order_by(ProductTrace.id.desc()).all()
    return render_template("admin_list.html", products=products)


@app.route("/admin/products/new", methods=["GET", "POST"])
def admin_new_product():
    """
    新增一条产品追溯信息，并生成对应二维码
    """
    if request.method == "POST":
        # 1. 生成追溯码
        trace_id = generate_trace_id()

        # 2. 从表单接收数据
        product = ProductTrace(
            trace_id=trace_id,
            product_name=request.form.get("product_name"),
            model=request.form.get("model"),
            material=request.form.get("material"),
            material_origin=request.form.get("material_origin"),
            material_batch=request.form.get("material_batch"),
            standard_code=request.form.get("standard_code"),
            function_desc=request.form.get("function_desc"),
            key_params=request.form.get("key_params"),
            prod_batch=request.form.get("prod_batch"),
            prod_date=request.form.get("prod_date"),
            prod_line=request.form.get("prod_line"),
            qc_result=request.form.get("qc_result"),
            qc_person=request.form.get("qc_person"),
            warranty_months=int(request.form.get("warranty_months") or 0),
        )

        # 3. 先保存记录
        db.session.add(product)
        db.session.commit()

        # 4. 生成二维码图片并更新记录
        qr_path = generate_qr(trace_id)
        product.qr_image_path = qr_path
        db.session.commit()

        return redirect(url_for("admin_products"))

    # GET 请求，返回表单页面
    return render_template("admin_form.html")


# ----------------- 对外扫码查询路由 -----------------
@app.route("/p/<trace_id>")
def trace_page(trace_id):
    """
    扫码后展示产品追溯信息
    """
    product = ProductTrace.query.filter_by(trace_id=trace_id).first()
    if not product:
        abort(404)

    # 记录扫码日志
    log = ScanLog(
        trace_id=trace_id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")
    )
    db.session.add(log)
    db.session.commit()

    return render_template("trace_page.html", product=product)


# ----------------- 入口 -----------------
if __name__ == "__main__":
    # debug=True 方便开发调试
    app.run(debug=True)
