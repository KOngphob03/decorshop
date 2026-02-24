from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'my_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root@localhost:3306/decorshop?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER_PRODUCTS = os.path.join('static', 'uploads', 'products')
UPLOAD_FOLDER_SLIPS = os.path.join('static', 'uploads', 'slips')
UPLOAD_FOLDER_PROFILES = os.path.join('static', 'uploads', 'profiles')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 

# สร้างโฟลเดอร์สำหรับเก็บไฟล์อัปโหลดถ้ายังไม่มี
os.makedirs(UPLOAD_FOLDER_PRODUCTS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_SLIPS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_PROFILES, exist_ok=True)

def process_and_save_image(file_obj, save_path):
    img = Image.open(file_obj)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(save_path, format="JPEG", quality=85)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# หมวดหมู่ฐานข้อมูล (Models)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    profile_image = db.Column(db.String(300), nullable=True)
    address = db.Column(db.Text, nullable=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(300), nullable=True)
    image_url_2 = db.Column(db.String(300), nullable=True)
    image_url_3 = db.Column(db.String(300), nullable=True)
    stock = db.Column(db.Integer, default=0)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    
    product = db.relationship('Product')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='เตรียมสินค้า') # เตรียมสินค้า, ขนส่งเข้ารับ, ระหว่างส่ง, จัดส่งสำเร็จ
    payment_slip = db.Column(db.String(300), nullable=True)
    address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    items = db.relationship('OrderItem', backref='order', lazy=True)
    user = db.relationship('User')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_booking = db.Column(db.Float, nullable=False)
    
    product = db.relationship('Product')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# หมวดหมู่หน้าเว็บ (Routes)
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        flash('เข้าสู่ระบบไม่สำเร็จ โปรดตรวจสอบชื่อผู้ใช้และรหัสผ่าน', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # ตรวจสอบว่ามีชื่อผู้ใช้นี้อยู่แล้วหรือไม่
        if User.query.filter_by(username=username).first():
            flash('ชื่อผู้ใช้นี้มีอยู่ในระบบแล้ว', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('สมัครสมาชิกสำเร็จ สามารถเข้าสู่ระบบได้เลย', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    products = Product.query.all()
    return render_template('admin_dashboard.html', products=products)

@app.route('/admin/add', methods=['POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    name = request.form.get('name')
    description = request.form.get('description')
    price = request.form.get('price')
    stock = request.form.get('stock')
    
    new_product = Product(name=name, description=description, price=float(price), stock=int(stock))
    db.session.add(new_product)
    db.session.flush() # บันทึกลงฐานข้อมูลชั่วคราวเพื่อดึงรหัสสินค้า (ID) ออกมาใช้งาน
    
    if 'image_file' in request.files:
        file = request.files['image_file']
        if file and file.filename != '':
            filename = f"{new_product.id}_1.jpg"
            filepath = os.path.join(UPLOAD_FOLDER_PRODUCTS, filename)
            process_and_save_image(file, filepath)
            new_product.image_url = url_for('static', filename=f'uploads/products/{filename}')
            
    if 'image_file_2' in request.files:
        file = request.files['image_file_2']
        if file and file.filename != '':
            filename = f"{new_product.id}_2.jpg"
            filepath = os.path.join(UPLOAD_FOLDER_PRODUCTS, filename)
            process_and_save_image(file, filepath)
            new_product.image_url_2 = url_for('static', filename=f'uploads/products/{filename}')
            
    if 'image_file_3' in request.files:
        file = request.files['image_file_3']
        if file and file.filename != '':
            filename = f"{new_product.id}_3.jpg"
            filepath = os.path.join(UPLOAD_FOLDER_PRODUCTS, filename)
            process_and_save_image(file, filepath)
            new_product.image_url_3 = url_for('static', filename=f'uploads/products/{filename}')
            
    db.session.commit()
    flash('เพิ่มสินค้าเรียบร้อยแล้ว', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
        
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.stock = int(request.form.get('stock'))
        
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '':
                filename = f"{product.id}_1.jpg"
                filepath = os.path.join(UPLOAD_FOLDER_PRODUCTS, filename)
                process_and_save_image(file, filepath)
                product.image_url = url_for('static', filename=f'uploads/products/{filename}')
                
        if 'image_file_2' in request.files:
            file = request.files['image_file_2']
            if file and file.filename != '':
                filename = f"{product.id}_2.jpg"
                filepath = os.path.join(UPLOAD_FOLDER_PRODUCTS, filename)
                process_and_save_image(file, filepath)
                product.image_url_2 = url_for('static', filename=f'uploads/products/{filename}')
                
        if 'image_file_3' in request.files:
            file = request.files['image_file_3']
            if file and file.filename != '':
                filename = f"{product.id}_3.jpg"
                filepath = os.path.join(UPLOAD_FOLDER_PRODUCTS, filename)
                process_and_save_image(file, filepath)
                product.image_url_3 = url_for('static', filename=f'uploads/products/{filename}')
                
        db.session.commit()
        flash('แก้ไขข้อมูลสินค้าเรียบร้อยแล้ว', 'success')
        return redirect(url_for('admin_dashboard'))
        
    return render_template('admin_edit_product.html', product=product)

@app.route('/admin/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('ลบสินค้าเรียบร้อยแล้ว', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/cart')
@login_required
def view_cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total_price = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = request.form.get('quantity', 1, type=int)
    
    if product.stock <= 0:
        flash('ขออภัย สินค้านี้หมดชั่วคราว', 'danger')
        return redirect(url_for('index'))
        
    if quantity <= 0:
        flash('จำนวนสินค้าไม่ถูกต้อง', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))
        
    if quantity > product.stock:
        flash(f'ขออภัย มีสินค้าในสต๊อกเพียง {product.stock} ชิ้น', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))
        
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if cart_item:
        if cart_item.quantity + quantity <= product.stock:
            cart_item.quantity += quantity
            flash('เพิ่มจำนวนสินค้าในตะกร้าแล้ว', 'success')
        else:
            flash(f'สินค้าในสต๊อกมีไม่เพียงพอ (คุณตะกร้าคุณมีแล้ว {cart_item.quantity} ชิ้น)', 'warning')
    else:
        new_cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity)
        db.session.add(new_cart_item)
        flash('เพิ่มสินค้าลงในตะกร้าแล้ว', 'success')
        
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/cart/remove/<int:cart_item_id>')
@login_required
def remove_from_cart(cart_item_id):
    cart_item = CartItem.query.get_or_404(cart_item_id)
    if cart_item.user_id != current_user.id:
        return redirect(url_for('view_cart'))
        
    db.session.delete(cart_item)
    db.session.commit()
    flash('ลบสินค้าออกจากตะกร้าแล้ว', 'success')
    return redirect(url_for('view_cart'))

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
            
        # สร้างบิลคำสั่งซื้อใหม่
        new_order = Order(user_id=current_user.id, total_price=total_price, address=address)
        db.session.add(new_order)
        db.session.flush() # บันทึกชั่วคราวเพื่อขอรหัสคำสั่งซื้อ (ID)
        
        # ตรวจสอบและบันทึกไฟล์สลิปโอนเงิน
        if 'payment_slip_file' in request.files:
            file = request.files['payment_slip_file']
            if file and file.filename != '':
                filename = f"{new_order.id}.jpg"
                filepath = os.path.join(UPLOAD_FOLDER_SLIPS, filename)
                process_and_save_image(file, filepath)
                new_order.payment_slip = url_for('static', filename=f'uploads/slips/{filename}')
        
        # ย้ายสินค้าจากตะกร้าเข้าสู่คำสั่งซื้อและหักสต๊อก
        for cart_item in cart_items:
            order_item = OrderItem(
                order_id=new_order.id, 
                product_id=cart_item.product_id, 
                quantity=cart_item.quantity, 
                price_at_booking=cart_item.product.price
            )
            # หักลบจำนวนสินค้าออกจากคลัง
            product = Product.query.get(cart_item.product_id)
            if product:
                product.stock = max(0, product.stock - cart_item.quantity)
                
            db.session.add(order_item)
            db.session.delete(cart_item)
            
        db.session.commit()
        flash('ชำระเงินเรียบร้อยแล้ว! สามารถติดตามสถานะได้ที่เมนูคำสั่งซื้อของคุณ', 'success')
        return redirect(url_for('my_orders'))
        
    return render_template('checkout.html', total_price=total_price)

@app.route('/orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders)

@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/order/update/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
        
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    valid_statuses = ['เตรียมสินค้า', 'ขนส่งเข้ารับ', 'ระหว่างส่ง', 'จัดส่งสำเร็จ']
    if new_status in valid_statuses:
        order.status = new_status
        db.session.commit()
        flash(f'อัปเดตสถานะคำสั่งซื้อ #{order.id} เป็น "{new_status}" เรียบร้อย', 'success')
    
    return redirect(url_for('admin_orders'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        # อัปเดตข้อมูลทั่วไปของผู้ใช้
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.phone = phone
        current_user.address = address
            
        # อัปโหลดและเปลี่ยนรูปโปรไฟล์ใหม่
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename != '':
                filename = f"user_{current_user.id}.jpg"
                filepath = os.path.join(UPLOAD_FOLDER_PROFILES, filename)
                process_and_save_image(file, filepath)
                current_user.profile_image = url_for('static', filename=f'uploads/profiles/{filename}')
                
        # ถ้าระบุรหัสผ่านใหม่มาด้วย ก็ให้ทำการเปลี่ยนรหัสผ่าน
        new_password = request.form.get('new_password')
        if new_password:
            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
            
        db.session.commit()
        flash('อัปเดตข้อมูลโปรไฟล์เรียบร้อยแล้ว', 'success')
        return redirect(url_for('profile'))
        
    return render_template('profile.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # สร้างบัญชีผู้ดูแลระบบ (Admin) เริ่มต้นไว้ ถ้ายังไม่มีในฐานข้อมูล
        if not User.query.filter_by(username='admin').first():
            hashed_pw = generate_password_hash('admin123', method='pbkdf2:sha256')
            admin = User(username='admin', password=hashed_pw, is_admin=True)
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)
