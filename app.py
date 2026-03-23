# นำเข้าเครื่องมือที่จำเป็น (ไม่ต้องแก้ไขส่วนนี้)
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from datetime import datetime
import os


# --- ตั้งค่าหลักของเว็บแอป ---

app = Flask(__name__)

# รหัสลับสำหรับเข้ารหัส Session (ควรเปลี่ยนก่อน deploy จริง)
app.config['SECRET_KEY'] = 'my_secret_key_123'

# ที่อยู่ฐานข้อมูล MySQL (รูปแบบ: ผู้ใช้@โฮสต์:พอร์ต/ชื่อฐานข้อมูล)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root@localhost:3306/decorshop?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ขนาดไฟล์สูงสุดที่รับได้จากการอัปโหลด (16 MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# โฟลเดอร์สำหรับเก็บรูปภาพแต่ละประเภท
UPLOAD_FOLDER_PRODUCTS = os.path.join('static', 'uploads', 'products')  # รูปสินค้า
UPLOAD_FOLDER_SLIPS    = os.path.join('static', 'uploads', 'slips')     # สลิปโอนเงิน
UPLOAD_FOLDER_PROFILES = os.path.join('static', 'uploads', 'profiles')  # รูปโปรไฟล์

# สร้างโฟลเดอร์อัตโนมัติถ้ายังไม่มี
os.makedirs(UPLOAD_FOLDER_PRODUCTS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_SLIPS,    exist_ok=True)
os.makedirs(UPLOAD_FOLDER_PROFILES, exist_ok=True)


# --- เชื่อมต่อฐานข้อมูลและระบบ Login ---

db = SQLAlchemy(app)  # ตัวจัดการฐานข้อมูล

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # ถ้ายังไม่ login ให้ redirect ไปหน้า /login


# --- ฟังก์ชันช่วยแปลงและบันทึกรูปภาพ ---

def process_and_save_image(file_obj, save_path):
    """
    รับไฟล์รูปภาพที่อัปโหลดมา → แปลงเป็น JPEG → บันทึกลงเซิร์ฟเวอร์
    รองรับทั้ง JPG, PNG (รวมถึงรูปที่มีพื้นหลังโปร่งใส)
    """
    img = Image.open(file_obj)
    if img.mode in ("RGBA", "P"):   # PNG โปร่งใสไม่สามารถบันทึกเป็น JPEG ได้โดยตรง
        img = img.convert("RGB")    # จึงต้องแปลงโหมดสีก่อน
    img.save(save_path, format="JPEG", quality=85)  # บันทึกแบบ JPEG คุณภาพ 85%


# --- โครงสร้างตารางในฐานข้อมูล (แต่ละ class = 1 ตารางใน MySQL) ---

# ตารางผู้ใช้งาน (ทั้งลูกค้าและแอดมิน)
class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)                    # รหัสผู้ใช้ (ไม่ซ้ำกัน)
    username      = db.Column(db.String(150), unique=True, nullable=False)     # ชื่อผู้ใช้
    password      = db.Column(db.String(150), nullable=False)                  # รหัสผ่าน (เข้ารหัสแล้ว)
    is_admin      = db.Column(db.Boolean, default=False)                       # True = แอดมิน
    first_name    = db.Column(db.String(100), nullable=True)
    last_name     = db.Column(db.String(100), nullable=True)
    phone         = db.Column(db.String(20),  nullable=True)
    profile_image = db.Column(db.String(300), nullable=True)                   # path รูปโปรไฟล์
    address       = db.Column(db.Text, nullable=True)                          # ที่อยู่จัดส่งเริ่มต้น


# ตารางสินค้า
class Product(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(150), nullable=False)    # ชื่อสินค้า
    description = db.Column(db.Text, nullable=True)            # รายละเอียด
    price       = db.Column(db.Float, nullable=False)          # ราคา
    image_url   = db.Column(db.String(300), nullable=True)     # รูปหลัก
    image_url_2 = db.Column(db.String(300), nullable=True)     # รูปเพิ่มเติม 2
    image_url_3 = db.Column(db.String(300), nullable=True)     # รูปเพิ่มเติม 3
    stock       = db.Column(db.Integer, default=0)             # จำนวนสต๊อกคงเหลือ


# ตารางสินค้าในตะกร้า (แต่ละแถว = สินค้า 1 ชิ้นในตะกร้าของผู้ใช้คนหนึ่ง)
class CartItem(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'),    nullable=False)  # ของใคร
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)  # สินค้าอะไร
    quantity   = db.Column(db.Integer, default=1)                                    # จำนวน

    product = db.relationship('Product')  # ดึงข้อมูลสินค้าได้โดยตรงผ่าน .product


# ตารางคำสั่งซื้อ (1 Order = 1 การชำระเงิน)
class Order(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_price  = db.Column(db.Float, nullable=False)                                # ยอดรวม
    status       = db.Column(db.String(50), default='เตรียมสินค้า')                  # สถานะการจัดส่ง
    payment_slip = db.Column(db.String(300), nullable=True)                           # path ไฟล์สลิป
    address      = db.Column(db.Text, nullable=False)                                 # ที่อยู่จัดส่ง
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)                   # วันที่สั่ง

    items = db.relationship('OrderItem', backref='order', lazy=True)  # รายการสินค้าใน order นี้
    user  = db.relationship('User')


# ตารางรายการสินค้าภายใน Order (1 Order มีได้หลาย OrderItem)
class OrderItem(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    order_id         = db.Column(db.Integer, db.ForeignKey('order.id'),   nullable=False)
    product_id       = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity         = db.Column(db.Integer, nullable=False)
    price_at_booking = db.Column(db.Float,   nullable=False)  # ราคา ณ วันที่สั่ง (เก็บไว้กันราคาเปลี่ยน)

    product = db.relationship('Product')


# บอกระบบว่าให้โหลดข้อมูลผู้ใช้จากฐานข้อมูลเมื่อมีการ login อยู่
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# จัดการ error เมื่ออัปโหลดไฟล์ใหญ่เกินกำหนด
@app.errorhandler(413)
def request_entity_too_large(error):
    flash('ไฟล์ที่อัปโหลดมีขนาดใหญ่เกินไป กรุณาใช้ไฟล์ที่มีขนาดไม่เกิน 16MB', 'danger')
    return redirect(request.referrer or url_for('index'))


# --- หน้าที่ทุกคนเข้าได้ ---

# หน้าแรก — แสดงสินค้าทั้งหมด
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)


# หน้ารายละเอียดสินค้า — ดึงสินค้าตาม ID ที่ระบุใน URL
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)  # ถ้าไม่มีสินค้า → แสดง 404
    return render_template('product_detail.html', product=product)


# --- เข้าสู่ระบบ / สมัครสมาชิก ---

# หน้าเข้าสู่ระบบ
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            # แอดมิน → ไปหน้า Dashboard | ลูกค้า → ไปหน้าแรก
            return redirect(url_for('admin_dashboard') if user.is_admin else url_for('index'))

        flash('เข้าสู่ระบบไม่สำเร็จ โปรดตรวจสอบชื่อผู้ใช้และรหัสผ่าน', 'danger')

    return render_template('login.html')


# หน้าสมัครสมาชิก
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # ตรวจสอบว่าชื่อผู้ใช้ซ้ำหรือไม่
        if User.query.filter_by(username=username).first():
            flash('ชื่อผู้ใช้นี้มีอยู่ในระบบแล้ว', 'danger')
            return redirect(url_for('register'))

        # เข้ารหัสรหัสผ่านก่อนบันทึก (ไม่เก็บรหัสผ่านจริงในฐานข้อมูล)
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        db.session.add(User(username=username, password=hashed_pw))
        db.session.commit()
        flash('สมัครสมาชิกสำเร็จ สามารถเข้าสู่ระบบได้เลย', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# ออกจากระบบ
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# --- ข้อมูลส่วนตัว ---

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # บันทึกข้อมูลทั่วไป
        current_user.first_name = request.form.get('first_name')
        current_user.last_name  = request.form.get('last_name')
        current_user.phone      = request.form.get('phone')
        current_user.address    = request.form.get('address')

        # อัปโหลดรูปโปรไฟล์ใหม่ (ถ้ามีการส่งมาด้วย)
        file = request.files.get('profile_image')
        if file and file.filename != '':
            filename = f"user_{current_user.id}.jpg"  # ตั้งชื่อไฟล์ตาม ID ผู้ใช้
            filepath = os.path.join(UPLOAD_FOLDER_PROFILES, filename)
            process_and_save_image(file, filepath)
            current_user.profile_image = url_for('static', filename=f'uploads/profiles/{filename}')

        # เปลี่ยนรหัสผ่าน — ทำเฉพาะเมื่อกรอก new_password มา
        new_password = request.form.get('new_password')
        if new_password:
            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')

        db.session.commit()
        flash('อัปเดตข้อมูลโปรไฟล์เรียบร้อยแล้ว', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html')


# --- จัดการสินค้า (เฉพาะแอดมิน) ---

# หน้า Dashboard แสดงสินค้าทั้งหมด
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    products = Product.query.all()
    return render_template('admin_dashboard.html', products=products)


# เพิ่มสินค้าใหม่
@app.route('/admin/add', methods=['POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        return redirect(url_for('index'))

    new_product = Product(
        name        = request.form.get('name'),
        description = request.form.get('description'),
        price       = float(request.form.get('price')),
        stock       = int(request.form.get('stock')),
    )
    db.session.add(new_product)
    db.session.flush()  # บันทึกชั่วคราวเพื่อให้ได้ ID ก่อน → ใช้ตั้งชื่อไฟล์รูป

    # วนรูป 3 ช่อง: รูปหลัก, รูป 2, รูป 3
    for slot, field in [(1, 'image_file'), (2, 'image_file_2'), (3, 'image_file_3')]:
        file = request.files.get(field)
        if file and file.filename != '':
            filename = f"{new_product.id}_{slot}.jpg"
            filepath = os.path.join(UPLOAD_FOLDER_PRODUCTS, filename)
            process_and_save_image(file, filepath)
            setattr(new_product, f'image_url{"" if slot == 1 else f"_{slot}"}',
                    url_for('static', filename=f'uploads/products/{filename}'))

    db.session.commit()
    flash('เพิ่มสินค้าเรียบร้อยแล้ว', 'success')
    return redirect(url_for('admin_dashboard'))


# แก้ไขข้อมูลสินค้า
@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))

    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name        = request.form.get('name')
        product.description = request.form.get('description')
        product.price       = float(request.form.get('price'))
        product.stock       = int(request.form.get('stock'))

        # อัปเดตรูป — เฉพาะช่องที่มีการส่งไฟล์ใหม่มาเท่านั้น
        for slot, field in [(1, 'image_file'), (2, 'image_file_2'), (3, 'image_file_3')]:
            file = request.files.get(field)
            if file and file.filename != '':
                filename = f"{product.id}_{slot}.jpg"
                filepath = os.path.join(UPLOAD_FOLDER_PRODUCTS, filename)
                process_and_save_image(file, filepath)
                setattr(product, f'image_url{"" if slot == 1 else f"_{slot}"}',
                        url_for('static', filename=f'uploads/products/{filename}'))

        db.session.commit()
        flash('แก้ไขข้อมูลสินค้าเรียบร้อยแล้ว', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_edit_product.html', product=product)


# ลบสินค้า
@app.route('/admin/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))

    product = Product.query.get_or_404(product_id)

    # ต้องลบข้อมูลที่อ้างอิงสินค้านี้ออกก่อน
    # มิฉะนั้นฐานข้อมูลจะ error (เพราะมี Foreign Key ชี้อยู่)
    CartItem.query.filter_by(product_id=product_id).delete()   # ลบออกจากตะกร้า
    OrderItem.query.filter_by(product_id=product_id).delete()  # ลบออกจากประวัติออเดอร์

    db.session.delete(product)
    db.session.commit()
    flash('ลบสินค้าเรียบร้อยแล้ว', 'success')
    return redirect(url_for('admin_dashboard'))


# --- จัดการออเดอร์ (เฉพาะแอดมิน) ---

# หน้ารายการออเดอร์ทั้งหมด (เรียงจากใหม่ไปเก่า)
@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_orders.html', orders=orders)


# อัปเดตสถานะการจัดส่ง
@app.route('/admin/order/update/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))

    order      = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    valid      = ['เตรียมสินค้า', 'ขนส่งเข้ารับ', 'ระหว่างส่ง', 'จัดส่งสำเร็จ']

    # รับเฉพาะสถานะที่กำหนดไว้เท่านั้น (ป้องกันการแก้ไขข้อมูลผิดปกติ)
    if new_status in valid:
        order.status = new_status
        db.session.commit()
        flash(f'อัปเดตสถานะคำสั่งซื้อ #{order.id} เป็น "{new_status}" เรียบร้อย', 'success')

    return redirect(url_for('admin_orders'))


# --- ตะกร้าสินค้า ---

# หน้าดูตะกร้า — คำนวณยอดรวมทั้งหมด
@app.route('/cart')
@login_required
def view_cart():
    cart_items  = CartItem.query.filter_by(user_id=current_user.id).all()
    total_price = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)


# เพิ่มสินค้าลงตะกร้า
@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product  = Product.query.get_or_404(product_id)
    quantity = request.form.get('quantity', 1, type=int)

    # ตรวจสอบความถูกต้องก่อนเพิ่ม
    if product.stock <= 0:
        flash('ขออภัย สินค้านี้หมดชั่วคราว', 'danger')
        return redirect(url_for('index'))

    if quantity <= 0:
        flash('จำนวนสินค้าไม่ถูกต้อง', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))

    if quantity > product.stock:
        flash(f'ขออภัย มีสินค้าในสต๊อกเพียง {product.stock} ชิ้น', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))

    # ถ้าสินค้านี้อยู่ในตะกร้าแล้ว → เพิ่มจำนวน, ถ้าไม่มี → เพิ่มรายการใหม่
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if cart_item:
        if cart_item.quantity + quantity <= product.stock:
            cart_item.quantity += quantity
            flash('เพิ่มจำนวนสินค้าในตะกร้าแล้ว', 'success')
        else:
            flash(f'สินค้าในสต๊อกมีไม่เพียงพอ (ในตะกร้ามีแล้ว {cart_item.quantity} ชิ้น)', 'warning')
    else:
        db.session.add(CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity))
        flash('เพิ่มสินค้าลงในตะกร้าแล้ว', 'success')

    db.session.commit()
    return redirect(url_for('index'))


# ลบสินค้าออกจากตะกร้า
@app.route('/cart/remove/<int:cart_item_id>')
@login_required
def remove_from_cart(cart_item_id):
    cart_item = CartItem.query.get_or_404(cart_item_id)

    # ตรวจสอบว่าเป็นตะกร้าของผู้ใช้คนนี้จริง (ป้องกันลบของคนอื่น)
    if cart_item.user_id != current_user.id:
        return redirect(url_for('view_cart'))

    db.session.delete(cart_item)
    db.session.commit()
    flash('ลบสินค้าออกจากตะกร้าแล้ว', 'success')
    return redirect(url_for('view_cart'))


# --- ชำระเงินและประวัติการสั่งซื้อ ---

# หน้าชำระเงิน
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('ไม่มีสินค้าในตะกร้า', 'warning')
        return redirect(url_for('view_cart'))

    total_price = sum(item.product.price * item.quantity for item in cart_items)

    if request.method == 'POST':
        address = request.form.get('address')
        if not address:
            flash('กรุณากรอกที่อยู่จัดส่ง', 'warning')
            return redirect(url_for('checkout'))

        # สร้าง Order ใหม่
        new_order = Order(user_id=current_user.id, total_price=total_price, address=address)
        db.session.add(new_order)
        db.session.flush()  # บันทึกชั่วคราวเพื่อให้ได้ Order ID ก่อน

        # อัปโหลดสลิปโอนเงิน (ถ้ามี)
        file = request.files.get('payment_slip_file')
        if file and file.filename != '':
            filename = f"{new_order.id}.jpg"  # ตั้งชื่อไฟล์ตาม Order ID
            filepath = os.path.join(UPLOAD_FOLDER_SLIPS, filename)
            process_and_save_image(file, filepath)
            new_order.payment_slip = url_for('static', filename=f'uploads/slips/{filename}')

        # ย้ายทุกรายการจากตะกร้า → OrderItem และหักจำนวนสต๊อก
        for cart_item in cart_items:
            db.session.add(OrderItem(
                order_id         = new_order.id,
                product_id       = cart_item.product_id,
                quantity         = cart_item.quantity,
                price_at_booking = cart_item.product.price,  # บันทึกราคา ณ วันที่ซื้อ
            ))
            product = Product.query.get(cart_item.product_id)
            if product:
                product.stock = max(0, product.stock - cart_item.quantity)  # หักสต๊อก (ไม่ให้ติดลบ)
            db.session.delete(cart_item)  # เคลียร์ตะกร้าหลังจ่ายเงิน

        db.session.commit()
        flash('ชำระเงินเรียบร้อยแล้ว! สามารถติดตามสถานะได้ที่เมนูคำสั่งซื้อของคุณ', 'success')
        return redirect(url_for('my_orders'))

    return render_template('checkout.html', total_price=total_price)


# หน้าประวัติคำสั่งซื้อของผู้ใช้
@app.route('/orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders)


# --- จุดเริ่มต้นการรันโปรแกรม ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # สร้างตารางทั้งหมดในฐานข้อมูล (ถ้ายังไม่มี)

        # สร้างบัญชี Admin เริ่มต้น (username: admin / password: admin123)
        # ทำครั้งเดียวตอนเริ่มต้น ถ้ามีแล้วจะข้ามไป
        if not User.query.filter_by(username='admin').first():
            hashed_pw = generate_password_hash('admin123', method='pbkdf2:sha256')
            db.session.add(User(username='admin', password=hashed_pw, is_admin=True))
            db.session.commit()

    app.run(debug=True)  # เปิดเว็บเซิร์ฟเวอร์ (debug=True = แสดง error detail)
