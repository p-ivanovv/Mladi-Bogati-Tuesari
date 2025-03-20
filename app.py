from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required
from flask import request, flash, redirect, url_for, session
from webforms import LoginForm, UserForm


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = "samo levski"

db = SQLAlchemy()
db.init_app(app)

class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return '<Name %r>' % self.name
    
class Shifts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(20), nullable=False)
    end_time = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('Users', backref='shifts')

    def __repr__(self):
        return '<Shift %r>' % self.id
    
class TimeOffRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200))
    status = db.Column(db.String(20), default='Pending')

with app.app_context():
	db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
	return Users.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
	form = LoginForm()
	if form.validate_on_submit():
		username = request.form['username']
		user = Users.query.filter_by(username=username).first()
		if user:
			if check_password_hash(user.password_hash, form.password.data):
				login_user(user)
				flash("Login Succesfull")
				session['username'] = username
				return redirect(url_for('dashboard'))
			else:
				flash("Wrong Password - Try Again")
		else:
			flash("User Not Found - Try Again")
	return render_template('login.html', form=form)

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
	logout_user()
	flash("You Have Been Logged Out")
	return redirect(url_for('login'))

@app.route('/user/add', methods=['GET', 'POST'])
def register():
	name = None
	form = UserForm()
	if form.validate_on_submit():
		user = Users.query.filter_by(email=form.email.data).first()
		if user is None:
			hashed_pw = generate_password_hash(form.password_hash.data)
			user = Users(username=form.username.data, name=form.name.data, email=form.email.data, password_hash=hashed_pw)
			db.session.add(user)
			db.session.commit()
		name = form.name.data
		form.name.data = ''
		form.username.data = ''
		form.email.data = ''
		form.password_hash.data = ''
		form.role.data = ''

		flash("User Added Successfully")
	return render_template("register.html", 
		form=form,
		name=name)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/calendar-data')
def calendar_data():
    return render_template('plan.html')

@app.route('/calendar-data-all')
def calendar_data_all():
    shifts = Shifts.query.all()
    return render_template('plan_all.html', shifts=shifts)

@app.route('/shift/add/<int:user_id>', methods=['GET', 'POST'])
def add_shift(user_id):
    if request.method == 'POST':
        date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        if date and start_time and end_time:
            new_shift = Shifts(date=date, start_time=start_time, end_time=end_time, user_id=user_id)
            db.session.add(new_shift)
            db.session.commit()
            flash("Shift added successfully!")
        else:
            flash("All fields are required!")
    shifts = Shifts.query.filter_by(user_id=user_id).all()
    return render_template('plan_all.html', shifts=shifts)

    return render_template('startingpage.html')
  
if __name__ == '__main__':
    app.run(debug=True)