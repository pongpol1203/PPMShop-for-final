from datetime import datetime
import os
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

CHAT_UPLOAD_FOLDER = 'static/uploads/chat'
UPLOAD_FOLDER = "static/uploads"
PDF_FOLDER = "static/pdfs"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# ตั้งค่าฐานข้อมูล SQLite
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ecommerce.db"
app.config['PDF_FOLDER'] = PDF_FOLDER
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(CHAT_UPLOAD_FOLDER, exist_ok=True)

# --- Model สำหรับระบบแชท ---
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # ID ผู้ส่ง
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # ID ผู้รับ (ถ้าเป็น Admin หรือส่งถึงผู้ใช้เฉพาะคน)
    message = db.Column(db.Text, nullable=True) # ข้อความ
    file_url = db.Column(db.String(255), nullable=True) # ไฟล์แนบ หรือ รูปภาพ
    file_type = db.Column(db.String(50), nullable=True) # ประเภทไฟล์ เช่น 'image', 'file'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow) # เวลาที่ส่ง

    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])
# --- ฐานข้อมูล Models (Tables) ---
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # ประเภทสินค้า
    brand = db.Column(db.String(50), nullable=True)       # 📌 เพิ่มฟิลด์แบรนด์ตรงนี้
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    is_best_seller = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=False)
    images = db.relationship('ProductImage', backref='product', cascade="all, delete-orphan")

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    image_url = db.Column(db.String(200), nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    lastname = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(100), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    address = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='รอตรวจสอบ', nullable=False)
    date = db.Column(db.String(50), nullable=False)
    slip_image = db.Column(db.String(200), nullable=True)
    pdf_invoice = db.Column(db.String(200), nullable=True)
    items = db.relationship("OrderItem", backref="order", lazy=True)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)


# สร้างตารางในฐานข้อมูลอัตโนมัติเมื่อรันครั้งแรก
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email="pongpol@gmail.com").first():
        admin = User(
            name="Pongpol",
            lastname="Sompan",
            phone="0973438173",
            email="pongpol@gmail.com",
            password="1234",
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

    if not Product.query.first():
        p1 = Product(
            name="IVE - [REVIVE+] 2nd Full Album [อัลบั้ม IVE]",
            description="",
            category="Album",
            price=3210,
            stock=2,
            image_url="static/uploads/REVIVE PLUS.jpg",
        )
        p2 = Product(
            name="IVE 2nd Digital Album Photobook+Jewel case ver. [LOVE DIVE]",
            description="- CD-R (1 แผ่น/ทั้งหมด 6 เวอร์ชัน) \n- โฟโต้บุ๊ก (1 เล่ม/ทั้งหมด 6 เวอร์ชัน)\n- HEART HOLOGRAM CARD :random 1 ใน 6\n- โปสเตอร์พับ (1 แผ่น/ทั้งหมด 6 เวอร์ชัน)\n- โฟโต้การ์ด (1 ใบ/ทั้งหมด 6 เวอร์ชัน)",
            category="Album",
            price=214,
            stock=10,
            image_url="static/uploads/LOVE DIVE.jpg",
        )
        db.session.add_all([p1, p2])
        db.session.commit()


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )

def generate_invoice_pdf(order):
    pdf_filename = f"invoice_{order.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    pdf_path = os.path.join(app.config["PDF_FOLDER"], pdf_filename)

    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter

    # หัวกระดาษใบเสร็จ
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "COMPANY RECEIPT / TAX INVOICE")
    
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, "E-Commerce Store Co., Ltd.")
    c.drawString(50, height - 85, "123/45 Sukhumvit Road, Bangkok, Thailand")
    c.drawString(50, height - 100, "Tax ID: 0123456789012 | Tel: 02-123-4567")

    c.drawString(400, height - 70, f"Order ID: #{order.id}")
    c.drawString(400, height - 85, f"Date: {order.date}")
    c.drawString(400, height - 100, f"Customer: {order.user_email}")

    c.line(50, height - 115, width - 50, height - 115)

    # รายการสินค้า
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, height - 135, "Description")
    c.drawString(300, height - 135, "Qty")
    c.drawString(360, height - 135, "Price")
    c.drawString(450, height - 135, "Subtotal")
    c.line(50, height - 145, width - 50, height - 145)

    y = height - 165
    c.setFont("Helvetica", 10)
    for item in order.items:
        c.drawString(50, y, item.product_name)
        c.drawString(300, y, str(item.quantity))
        c.drawString(360, y, f"{item.price:,.2f}")
        c.drawString(450, y, f"{item.subtotal:,.2f}")
        y -= 20

    c.line(50, y - 5, width - 50, y - 5)

    # คำนวณราคาและ VAT 7%
    y -= 25
    subtotal_no_vat = order.total_price / 1.07
    vat_amount = order.total_price - subtotal_no_vat

    c.drawString(350, y, "Subtotal:")
    c.drawString(450, y, f"{subtotal_no_vat:,.2f} THB")
    y -= 18
    c.drawString(350, y, "VAT (7%):")
    c.drawString(450, y, f"{vat_amount:,.2f} THB")
    y -= 18
    c.setFont("Helvetica-Bold", 11)
    c.drawString(350, y, "Total Amount:")
    c.drawString(450, y, f"{order.total_price:,.2f} THB")

    c.save()
    return url_for("static", filename=f"pdfs/{pdf_filename}")
# --- Routes ---

@app.route("/")
def index():
    selected_category = request.args.get("category")
    selected_brand = request.args.get("brand")  # 📌 รับค่าแบรนด์ที่ลูกค้าคลิกเลือก

    # ดึงหมวดหมู่และแบรนด์ที่ไม่ซ้ำกันสำหรับทำปุ่มกดกรอง
    categories = [c[0] for c in db.session.query(Product.category.distinct()).all()]
    brands = [b[0] for b in db.session.query(Product.brand.distinct()).all() if b[0]]  # ดึงแบรนด์ที่ไม่ใช่ค่าว่าง

    # ตั้งต้น query สินค้าทั้งหมด
    query = Product.query

    # ถ้ามีการเลือกหมวดหมู่
    if selected_category:
        query = query.filter_by(category=selected_category)
    
    # 📌 ถ้ามีการเลือกแบรนด์
    if selected_brand:
        query = query.filter_by(brand=selected_brand)

    all_products = query.all()
    
    # สินค้าขายดีและมาใหม่ (แสดงปกติ)
    best_products = Product.query.filter_by(is_best_seller=True).all()
    new_products = Product.query.filter_by(is_new=True).all()

    # 📍 ดึงสินค้าที่เป็นสินค้าขายดีหรือสินค้ามาใหม่ มาทำ Banner (จำกัดสัก 5 ชิ้น)
    banner_products = Product.query.filter((Product.is_best_seller == True) | (Product.is_new == True)).limit(5).all()

    return render_template(
        "index.html",
        all_products=all_products,
        best_products=best_products,
        new_products=new_products,
        banner_products=banner_products,
        categories=categories,
        brands=brands,  # 📌 ส่งรายชื่อแบรนด์ไปหน้าเว็บ
        selected_category=selected_category,
        selected_brand=selected_brand  # 📌 ส่งค่าแบรนด์ที่เลือกไปหน้าเว็บ
    )

# 1. หน้าแชทของลูกค้า (คุยกับ Admin)
@app.route('/chat', methods=['GET', 'POST'])
def customer_chat():
    if 'user_id' not in session:
        flash('กรุณาล็อกอินก่อนใช้งานระบบแชท', 'warning')
        return redirect(url_for('login', next=request.path))
    
    current_user_id = session['user_id']
    
    if request.method == 'POST':
        msg_text = request.form.get('message', '').strip()
        file = request.files.get('file')
        file_url = None
        file_type = None

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            # ป้องกันชื่อไฟล์ซ้ำด้วย timestamp
            saved_filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
            file_path = os.path.join(CHAT_UPLOAD_FOLDER, saved_filename)
            file.save(file_path)
            file_url = f"static/uploads/chat/{saved_filename}"

            # เช็คประเภทไฟล์ว่าเป็นรูปภาพหรือไฟล์ทั่วไป
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                file_type = 'image'
            else:
                file_type = 'file'

        if msg_text or file_url:
            new_msg = ChatMessage(
                sender_id=current_user_id,
                message=msg_text,
                file_url=file_url,
                file_type=file_type
            )
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for('customer_chat'))

    # ดึงข้อความทั้งหมดของลูกค้ารายนี้ (ทั้งที่ส่งเอง และที่ Admin ตอบกลับ)
    messages = ChatMessage.query.filter(
        (ChatMessage.sender_id == current_user_id) | (ChatMessage.receiver_id == current_user_id)
    ).order_by(ChatMessage.timestamp.asc()).all()

    return render_template('chat.html', messages=messages)


# 2. หน้าแชทของ Admin (เลือกคุยตามรายชื่อลูกค้า)
@app.route('/admin/chat', methods=['GET', 'POST'])
@app.route('/admin/chat/<int:user_id>', methods=['GET', 'POST'])
def admin_chat(user_id=None):
    # 1. เช็คสิทธิ์แอดมิน
    if not session.get('admin') and not session.get('is_admin'):
        flash('สำหรับผู้ดูแลระบบเท่านั้น', 'danger')
        return redirect(url_for('index'))

    admin_id = session.get('user_id') or 1  # กำหนด ID แอดมินกลาง

    # ส่งข้อความจากแอดมินหาลูกค้า
    if request.method == 'POST' and user_id:
        msg_text = request.form.get('message', '').strip()
        file = request.files.get('file')
        file_url = None
        file_type = None

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            saved_filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
            file_path = os.path.join(CHAT_UPLOAD_FOLDER, saved_filename)
            file.save(file_path)
            file_url = f"static/uploads/chat/{saved_filename}"

            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                file_type = 'image'
            else:
                file_type = 'file'

        if msg_text or file_url:
            new_msg = ChatMessage(
                sender_id=admin_id,
                receiver_id=user_id,
                message=msg_text,
                file_url=file_url,
                file_type=file_type
            )
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for('admin_chat', user_id=user_id))

    # 2. ดึงรายชื่อผู้ใช้ทั้งหมดที่เคยส่งข้อความเข้ามา (ไม่มี .filter(User.is_admin) แล้ว)
    chat_users = User.query.join(
        ChatMessage, ChatMessage.sender_id == User.id
    ).distinct().all()

    # 3. ดึงข้อความแชทของลูกค้าคนที่เลือก
    messages = []
    selected_user = None
    if user_id:
        selected_user = User.query.get(user_id)
        messages = ChatMessage.query.filter(
            ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == None)) |
            ((ChatMessage.sender_id == admin_id) & (ChatMessage.receiver_id == user_id)) |
            ((ChatMessage.sender_id == user_id) & (ChatMessage.receiver_id == admin_id))
        ).order_by(ChatMessage.timestamp.asc()).all()

    # ส่งข้อมูลทั้งหมดไปแสดงผลที่หน้าจอแอดมิน (รอบเดียวจบ)
    return render_template('admin_chat.html', chat_users=chat_users, selected_user=selected_user, messages=messages)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        lastname = request.form["lastname"]
        phone = request.form["phone"]
        email = request.form["email"]
        password = request.form["password"]

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Gmail นี้ถูกใช้งานไปแล้ว", "danger")
            return redirect(url_for("register"))

        new_user = User(
            name=name,
            lastname=lastname,
            phone=phone,
            email=email,
            password=password,
        )
        db.session.add(new_user)
        db.session.commit()

        flash("สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        input_user = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=input_user).first()
        
        if user and user.password == password:
            # 📌 บันทึกข้อมูลลง Session ให้ครบถ้วนตรงกับที่หน้า HTML เรียกใช้
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_email'] = user.email  # <--- เพิ่มบรรทัดนี้สำคัญมาก!
            
            # เช็คสิทธิ์แอดมิน
            if user.email == 'pongpol@gmail.com' or user.is_admin:
                session['admin'] = True
            
            flash('เข้าสู่ระบบสำเร็จ!', 'success')
            return redirect(url_for('index'))
        else:
            flash('อีเมลหรือรหัสผ่านไม่ถูกต้อง', 'danger')
            
    return render_template('login.html')

@app.route("/logout")
def logout():
    session.clear()
    flash("ออกจากระบบเรียบร้อยแล้ว", "info")
    return redirect(url_for("index"))


@app.route("/add_to_cart/<int:product_id>")
def add_to_cart(product_id):
    if "user_email" not in session:
        flash("กรุณาเข้าสู่ระบบก่อนสั่งซื้อสินค้า", "warning")
        return redirect(url_for("login"))

    if "cart" not in session:
        session["cart"] = {}

    prod_id_str = str(product_id)
    if prod_id_str in session["cart"]:
        session["cart"][prod_id_str] += 1
    else:
        session["cart"][prod_id_str] = 1

    session.modified = True
    flash("เพิ่มสินค้าลงตะกร้าแล้ว", "success")
    return redirect(url_for("cart"))

@app.route("/cart", methods=["GET", "POST"])
def cart():
    if "user_email" not in session:
        return redirect(url_for("login"))

    if "cart" not in session:
        session["cart"] = {}

    total_price = 0  
    subtotal_price = 0
    vat_amount = 0

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update":
            product_id = request.form.get("product_id")
            change = int(request.form.get("change"))
            if product_id in session["cart"]:
                session["cart"][product_id] += change
                if session["cart"][product_id] <= 0:
                    del session["cart"][product_id]
            session.modified = True
            return redirect(url_for("cart"))

        address = request.form.get("address")
        if address:
            cart_data = session.get("cart", {})
            if not cart_data:
                flash("ตะกร้าสินค้าว่างเปล่า", "warning")
                return redirect(url_for("cart"))

            slip_filename = None
            if "slip" in request.files:
                file = request.files["slip"]
                if file and file.filename != "":
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    if "." in file.filename:
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        if ext not in ['png', 'jpg', 'jpeg', 'jfif']:
                            ext = 'jpg'
                    else:
                        ext = 'jpg'
                        
                    slip_filename = f"slip_{timestamp}.{ext}"
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], slip_filename))

            if not slip_filename:
                flash("กรุณาแนบสลิปหลักฐานการโอนเงิน", "danger")
                return redirect(url_for("cart"))

            items_to_save = []
            for prod_id_str, qty in cart_data.items():
                prod_id = int(prod_id_str)
                product = Product.query.get(prod_id)
                if product:
                    if product.stock < qty:
                        flash(f"สินค้า {product.name} ในคลังมีไม่พอ (เหลือ {product.stock} ชิ้น)", "danger")
                        return redirect(url_for("cart"))

                    subtotal = product.price * qty  # ราคานี้รวม VAT แล้ว
                    total_price += subtotal
                    items_to_save.append({
                        "product_name": product.name,
                        "price": product.price,
                        "quantity": qty,
                        "subtotal": subtotal,
                    })
                    product.stock -= qty

            # บันทึกคำสั่งซื้อใหม่ (ใช้ราคารวมสุทธิโดยตรง ไม่บวกเพิ่ม)
            new_order = Order(
                user_email=session["user_email"],
                total_price=total_price,
                address=address,
                status="รอการตรวจสอบการชำระเงิน",
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                slip_image=slip_filename,  
            )
            db.session.add(new_order)
            db.session.commit()

            for item in items_to_save:
                order_item = OrderItem(
                    order_id=new_order.id,
                    product_name=item["product_name"],
                    price=item["price"],
                    quantity=item["quantity"],
                    subtotal=item["subtotal"],
                )
                db.session.add(order_item)
            db.session.commit()

            session["cart"] = {}
            flash("สั่งซื้อสินค้าและแนบสลิปสำเร็จ!", "success")
            return redirect(url_for("my_orders"))

    # ส่วนการแสดงผลหน้าตะกร้า (GET)
    cart_data = session.get("cart", {})
    cart_items = []

    for prod_id_str, qty in cart_data.items():
        prod_id = int(prod_id_str)
        product = Product.query.get(prod_id)
        if product:
            subtotal = product.price * qty
            cart_items.append({
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "quantity": qty,
                "subtotal": subtotal,
                "image_url": product.image_url,
            })
            total_price += subtotal  # ยอดรวมสุทธิที่รวม VAT แล้ว

    # คำนวณถอด VAT ออกมาแสดงผล (กรณีราคาตั้งต้นรวม VAT แล้ว)
    # สูตร: ราคาก่อน VAT = ราคารวม / 1.07
    # ค่า VAT = ราคารวม - ราคาก่อน VAT
    subtotal_price = total_price / 1.07
    vat_amount = total_price - subtotal_price

    return render_template(
        "cart.html", 
        cart_items=cart_items, 
        subtotal_price=subtotal_price,
        vat_amount=vat_amount,
        total_price=total_price
    )

@app.route("/admin/restock/<int:product_id>", methods=["POST"])
def restock_product(product_id):
    # ปรับให้เช็คสิทธิ์ admin เหมือนกับฟังก์ชัน admin_dashboard ของคุณ
    if not session.get("admin"):
        flash("สำหรับผู้ดูแลระบบเท่านั้น", "danger")
        return redirect(url_for("login"))
        
    product = Product.query.get_or_404(product_id)
    try:
        add_stock = int(request.form.get("add_stock", 0))
        if add_stock > 0:
            product.stock += add_stock
            db.session.commit()
            flash(f"เติมสต็อกสินค้า {product.name} สำเร็จ (+{add_stock} ชิ้น)", "success")
        else:
            flash("จำนวนที่ต้องการเติมต้องมากกว่า 0", "warning")
    except ValueError:
        flash("กรุณากรอกตัวเลขให้ถูกต้อง", "danger")
        
    return redirect(url_for("admin_dashboard"))

@app.route("/my_orders")
def my_orders():
    if "user_email" not in session:
        return redirect(url_for("login"))

    user_orders = Order.query.filter_by(user_email=session["user_email"]).all()
    return render_template("orders.html", orders=user_orders)


# หน้าแดชบอร์ดแอดมิน (จัดการสินค้า + เพิ่มสินค้าพร้อมหลายรูป)
@app.route("/admin/dashboard", methods=["GET", "POST"])
def admin_dashboard():
    if not session.get("admin"):
        flash("สำหรับผู้ดูแลระบบเท่านั้น", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        category = request.form["category"]
        
        # 📌 1. รับค่าแบรนด์จากฟอร์ม
        brand = request.form.get("brand", "") 

        price = float(request.form["price"])
        stock = int(request.form["stock"])

        # 📌 2. ปรับวิธีเช็กสถานะ Checkbox ให้รองรับทุกรูปแบบ (1, on, true) อย่างครอบคลุม
        is_best_seller = True if request.form.get("is_best_seller") in ["1", "on", "true"] else False
        is_new = True if request.form.get("is_new") in ["1", "on", "true"] else False

        # 1. จัดการรูปภาพหลัก (หน้าปก)
        main_image_filename = "default.jpg"
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename != "" and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S_")
                main_image_filename = timestamp + filename
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], main_image_filename))

        # 3. สร้าง Product ใหม่พร้อมสถานะพิเศษ
        new_product = Product(
            name=name,
            description=description,
            category=category,
            brand=brand,
            price=price,
            stock=stock,
            image_url=url_for("static", filename=f"uploads/{main_image_filename}"),
            is_best_seller=is_best_seller,
            is_new=is_new
        )
        db.session.add(new_product)
        db.session.commit()

        # 2. จัดการรูปภาพเพิ่มเติมหลายรูป (Gallery)
        if "extra_images" in request.files:
            files = request.files.getlist("extra_images")
            for file in files:
                if file and file.filename != "" and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S_")
                    extra_filename = timestamp + filename
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], extra_filename))

                    new_image = ProductImage(
                        product_id=new_product.id,
                        image_url=url_for("static", filename=f"uploads/{extra_filename}"),
                    )
                    db.session.add(new_image)
            db.session.commit()

        flash("เพิ่มสินค้าและรูปภาพทั้งหมดสำเร็จ", "success")
        return redirect(url_for("admin_dashboard"))

    # ส่วนประมวลผลข้อมูลแสดงผลหน้า Dashboard (คงเดิมตามโค้ดของคุณ)
    products = Product.query.all()
    orders = Order.query.all()
    all_users = User.query.all()

    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    current_month_str = now.strftime("%Y-%m")
    current_year_str = now.strftime("%Y")

    daily_sales = 0
    monthly_sales = 0
    yearly_sales = 0
    total_sales = 0

    for order in orders:
        if order.status == "ยกเลิกออเดอร์ (สลิปไม่ถูกต้อง)" or order.status == "Rejected":
            continue

        total_sales += order.total_price

        order_date_prefix = order.date[:10]
        order_month_prefix = order.date[:7]
        order_year_prefix = order.date[:4]

        if order_date_prefix == today_str:
            daily_sales += order.total_price
        if order_month_prefix == current_month_str:
            monthly_sales += order.total_price
        if order_year_prefix == current_year_str:
            yearly_sales += order.total_price

    all_users = User.query.all()

    return render_template(
        "admin_dashboard.html",
        products=products,
        daily_sales=daily_sales,
        monthly_sales=monthly_sales,
        yearly_sales=yearly_sales,
        total_sales=total_sales,
        all_users=all_users
    )

@app.route('/admin/start_chat/<int:user_id>', methods=['GET', 'POST'])
def admin_start_chat(user_id):
    if not session.get('admin'):
        flash('สำหรับผู้ดูแลระบบเท่านั้น', 'danger')
        return redirect(url_for('login'))
    
    target_user = User.query.get_or_404(user_id)
    admin_id = session.get('user_id') 
    
    if request.method == 'POST':
        msg_content = request.form.get('message', '').strip()
        file_url = None
        file_type = None
        
        # 📷 จัดการอัปโหลดรูปภาพ
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S_")
                chat_filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], chat_filename))
                file_url = url_for('static', filename=f'uploads/{chat_filename}')
                file_type = 'image' # บันทึกประเภทเป็นรูปภาพ

        # บันทึกข้อความหรือไฟล์ลงฐานข้อมูล
        if msg_content or file_url:
            new_msg = ChatMessage(
                sender_id=admin_id,
                receiver_id=target_user.id,
                message=msg_content if msg_content else None,
                file_url=file_url,
                file_type=file_type
            )
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for('admin_start_chat', user_id=target_user.id))
            
    messages = ChatMessage.query.filter(
        ((ChatMessage.sender_id == admin_id) & (ChatMessage.receiver_id == target_user.id)) |
        ((ChatMessage.sender_id == target_user.id) & (ChatMessage.receiver_id == admin_id))
    ).order_by(ChatMessage.timestamp.asc()).all()
    
    return render_template('admin_chat_detail.html', target_user=target_user, messages=messages)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template("product_detail.html", product=product)

# --- เพิ่ม Route สำหรับแก้ไขข้อมูลสินค้า เพิ่ม/ลด สต็อก และจัดการรูปภาพเพิ่มหลังจากอัปเดตแล้ว ---
@app.route("/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    if not session.get("admin"):
        flash("สำหรับผู้ดูแลระบบเท่านั้น", "danger")
        return redirect(url_for("login"))

    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        product.name = request.form.get("name")
        product.category = request.form.get("category")
        product.brand = request.form.get("brand")
        product.description = request.form.get("description")
        product.price = float(request.form.get("price") or 0)
        product.stock = int(request.form.get("stock") or 0)
        
        # 📌 [จุดที่แก้ไข] ปรับการรับค่าสถานะพิเศษให้รองรับทั้ง 1, on หรือ true อย่างแม่นยำ
        product.is_best_seller = True if request.form.get("is_best_seller") in ["1", "on", "true"] else False
        product.is_new = True if request.form.get("is_new") in ["1", "on", "true"] else False

        # 1. จัดการเปลี่ยนรูปภาพหลัก (หน้าปก) ถ้ามีการอัปโหลดใหม่
        image_file = request.files.get("image")
        if image_file and image_file.filename != "" and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S_")
            main_image_filename = timestamp + filename
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], main_image_filename))
            product.image_url = url_for("static", filename=f"uploads/{main_image_filename}")

        # 2. เพิ่มส่วนจัดการรูปภาพเสริม (Gallery) ที่อัปโหลดเพิ่มตอนแก้ไข
        if "extra_images" in request.files:
            files = request.files.getlist("extra_images")
            for file in files:
                if file and file.filename != "" and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S_")
                    extra_filename = timestamp + filename
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], extra_filename))

                    new_image = ProductImage(
                        product_id=product.id,
                        image_url=url_for("static", filename=f"uploads/{extra_filename}"),
                    )
                    db.session.add(new_image)

        db.session.commit()
        flash("แก้ไขข้อมูลสินค้าสำเร็จ!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("edit_product.html", product=product)

# Route ลบรูปภาพย่อยของสินค้าแต่ละรูป
@app.route("/admin/delete_product_image/<int:image_id>")
def delete_product_image(image_id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    img = ProductImage.query.get_or_404(image_id)
    product_id = img.product_id
    db.session.delete(img)
    db.session.commit()

    flash("ลบรูปภาพเพิ่มเติมเรียบร้อย", "info")
    return redirect(url_for("edit_product", product_id=product_id))


@app.route("/admin/sales_report", methods=["GET"])
def sales_report():
    if not session.get("admin"):
        flash("สำหรับผู้ดูแลระบบเท่านั้น", "danger")
        return redirect(url_for("login"))

    filter_type = request.args.get("filter_type", "day")
    selected_date = request.args.get("selected_date", "")

    now = datetime.now()
    if not selected_date:
        if filter_type == "day":
            selected_date = now.strftime("%Y-%m-%d")
        elif filter_type == "month":
            selected_date = now.strftime("%Y-%m")
        elif filter_type == "year":
            selected_date = now.strftime("%Y")

    orders = Order.query.all()
    filtered_orders = []
    total_sales_amount = 0
    product_summary = {}

    for order in orders:
        if order.status == "ยกเลิกออเดอร์ (สลิปไม่ถูกต้อง)" or order.status == "Rejected":
            continue

        order_date_str = order.date[:10]
        order_month_str = order.date[:7]
        order_year_str = order.date[:4]

        is_match = False
        if filter_type == "day" and order_date_str == selected_date:
            is_match = True
        elif filter_type == "month" and order_month_str == selected_date:
            is_match = True
        elif filter_type == "year" and order_year_str == selected_date:
            is_match = True
        elif filter_type == "all":
            is_match = True

        if is_match:
            filtered_orders.append(order)
            total_sales_amount += order.total_price

            for item in order.items:
                p_name = item.product_name
                if p_name not in product_summary:
                    product_summary[p_name] = {"quantity": 0, "total_price": 0}
                product_summary[p_name]["quantity"] += item.quantity
                product_summary[p_name]["total_price"] += item.subtotal

    return render_template(
        "admin_sales_report.html",
        orders=filtered_orders,
        total_sales_amount=total_sales_amount,
        product_summary=product_summary,
        filter_type=filter_type,
        selected_date=selected_date,
    )


@app.route("/admin/delete_product/<int:product_id>")
def delete_product(product_id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()

    flash("ลบสินค้าเรียบร้อย", "info")
    return redirect(url_for("admin_dashboard"))


@app.route('/admin/orders', methods=['GET', 'POST'])
def admin_orders():
    if not session.get('admin'):
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        new_status = request.form.get('status')
        
        order = Order.query.get(order_id)
        if order:
            # 🛡️ 1. ล็อกสถานะ: ถ้าออเดอร์เคยถูก "ยกเลิกสินค้า" หรือ "จัดส่งแล้ว" ไปแล้ว ห้ามเปลี่ยนสถานะกลับเด็ดขาด
            if order.status in ['ยกเลิกสินค้า', 'จัดส่งแล้ว']:
                flash(f'คำสั่งซื้อ #{order.id} ถูกปิดการแก้ไขแล้ว (สถานะเป็น {order.status})', 'danger')
                return redirect(url_for('admin_orders'))
            
            # 📦 2. ถ้าแอดมินกดเปลี่ยนเป็น "ยกเลิกสินค้า" ให้คืนสต็อกเข้าคลัง
            if new_status == 'ยกเลิกสินค้า':
                for item in order.items:
                    product = Product.query.filter_by(name=item.product_name).first()
                    if product:
                        product.stock += item.quantity # คืนจำนวนสินค้ากลับเข้าคลัง
                
                # 💰 3. เคลียร์ยอดเงิน: เซ็ตราคารวมของออเดอร์นี้เป็น 0 (ไม่นำไปบวกในยอดขายรวม)
                order.total_price = 0.0 

            order.status = new_status
            db.session.commit()
            flash(f'อัปเดตสถานะคำสั่งซื้อ #{order.id} เรียบร้อยแล้ว (คืนสต็อกและอัปเดตระบบสำเร็จ)', 'success')
            
        return redirect(url_for('admin_orders'))
        
    # 📌 แนะนำให้เพิ่ม .order_by(Order.id.desc()) ตรงนี้ เพื่อให้ออเดอร์ใหม่ล่าสุดขึ้นมาอยู่บนสุดของตารางแอดมินครับ!
    orders = Order.query.order_by(Order.id.desc()).all()
    
    # 📊 คำนวณรายรับรวมเฉพาะออเดอร์ที่ "ชำระเงินครบถ้วน" หรือ "จัดส่งแล้ว" เท่านั้น
    total_revenue = db.session.query(db.func.sum(Order.total_price))\
        .filter(Order.status.in_(['ชำระเงินครบถ้วน', 'จัดส่งแล้ว']))\
        .scalar() or 0.0

    return render_template('admin_orders.html', orders=orders, total_revenue=total_revenue)

@app.route('/order/receipt/<int:order_id>')
def view_receipt(order_id):
    if not session.get('admin') and not session.get('user_email'):
        flash('กรุณาเข้าสู่ระบบก่อน', 'danger')
        return redirect(url_for('login'))
        
    order = Order.query.get_or_404(order_id)
    total_price = order.total_price
    vat_amount = total_price * 7 / 107  # คำนวณ VAT 7% แยกออกมา
    net_price = total_price - vat_amount
    
    return render_template('receipt.html', order=order, vat_amount=vat_amount, net_price=net_price)

@app.route("/admin/order/<int:order_id>/reject", methods=["POST"])
def reject_order(order_id):
    if not session.get("admin"):
        flash("สำหรับผู้ดูแลระบบเท่านั้น", "danger")
        return redirect(url_for("login"))

    order = Order.query.get_or_404(order_id)

    if order.status != "Rejected":
        for item in order.items:
            # ค้นหาตามชื่อสินค้าเพื่อความถูกต้อง หรือใช้ product_id หากเก็บไว้
            product = Product.query.filter_by(name=item.product_name).first()
            if product:
                product.stock += item.quantity

        order.status = "Rejected"
        db.session.commit()

        flash(f"ปฏิเสธคำสั่งซื้อ #{order.id} เรียบร้อย (คืนสินค้าเข้าคลังและตัดยอดขายออกแล้ว)", "warning")
    else:
        flash("คำสั่งซื้อนี้ถูกปฏิเสธไปแล้ว", "info")

    return redirect(url_for("admin_orders"))


if __name__ == "__main__":
    app.run(debug=True)