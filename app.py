from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
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
    role = db.Column(db.String(20), nullable=False, default='employee')

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

@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update(id):
	form = UserForm()
	name_to_update = Users.query.get_or_404(id)
	if request.method == "POST":
		name_to_update.name = request.form['name']
		name_to_update.email = request.form['email']
		name_to_update.username = request.form['username']
		try:
			db.session.commit()
			flash("User Updated Successfully!")
			return render_template("update.html", form=form, name_to_update = name_to_update, id=id)
		except:
			flash("Error. Looks like there was a problem - try again.")
			return render_template("update.html", form=form, name_to_update = name_to_update, id=id)
	else:
		return render_template("update.html", form=form, name_to_update = name_to_update, id = id)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
	if id == current_user.id:
		user_to_delete = Users.query.get_or_404(id)
		name = None
		form = UserForm()

		try:
			db.session.delete(user_to_delete)
			db.session.commit()
			flash("User Deleted Successfully!!")

			our_users = Users.query.order_by(Users.date_added)
			return render_template("add_user.html", form=form, name=name, our_users=our_users)

		except:
			flash("There was a problem deleting user - try again.")
			return render_template("add_user.html", form=form, name=name,our_users=our_users)
	else:
		flash("Sorry, you can't delete that user! ")
		return redirect(url_for('dashboard'))

@app.route('/user/add', methods=['GET', 'POST'])
def register():
    name = None
    form = UserForm()
    if form.validate_on_submit():  
        user = Users.query.filter_by(email=form.email.data).first()
        if user is None:  
            hashed_pw = generate_password_hash(form.password_hash.data)
            user = Users(
                username=form.username.data,
                name=form.name.data,
                email=form.email.data,
                password_hash=hashed_pw,
                role=form.role.data
            )
            db.session.add(user)  
            db.session.commit()  
            flash("User Added Successfully")
            return redirect(url_for('login')) 

    return render_template("register.html", form=form, name=name)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/request_time_off', methods=['GET', 'POST'])
@login_required
def request_time_off():
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason')
        if start_date and end_date and reason:
            new_request = TimeOffRequest(user_id=current_user.id, start_date=start_date, end_date=end_date, reason=reason)
            db.session.add(new_request)
            db.session.commit()
            flash("Request submitted successfully!")
        else:
            flash("All fields are required!")
    requests = TimeOffRequest.query.filter_by(user_id=current_user.id).all()
    return render_template('request_time_off.html', requests=requests)
    #return render_template('request_time_off.html')

@app.route('/requests', methods=['GET', 'POST'])
@login_required
def requests():
    if current_user.role != 'manager':
        flash("You are not authorized to view this page.")
        return url_for('shifts')
    requests = TimeOffRequest.query.all()
    return render_template('view_time_off_requests.html', requests=requests)

@app.route('/view_time_off_request', methods=['GET', 'POST'])
@login_required
def view_time_request():
    if current_user.role != 'manager':
        flash("You are not authorized to view this page.")
        return url_for('shifts')
    if request.method == 'POST':
        request_id = request.form.get('request_id')
        action = request.form.get('action')
        request = TimeOffRequest.query.get(request_id)
        if action == 'approve':
            request.status = 'Approved'
        elif action == 'reject':
            request.status = 'Rejected'

        db.session.commit()
        flash("Request updated successfully!")
        return url_for('requests')
    return render_template('view_time_off_request.html', requests=requests)

@app.route('/')
def home():
    return render_template('startingpage.html')

@app.route('/calendar-data')
@login_required
def calendar_data():
    if session.get('username'):
        user = Users.query.filter_by(username=session['username']).first()
        if user.role == 'Employee':
            shifts = Shifts.query.filter_by(user_id=user.id).all()
            return render_template('plan.html', shifts=shifts)
    else:
        flash("Please log in to access this page.")
        return redirect(url_for('login'))

@app.route('/calendar-data-all')
@login_required
def calendar_data_all():
    if session.get('username'):
        user = Users.query.filter_by(username=session['username']).first()
        if user.role == 'Manager':
            shifts = Shifts.query.all()
            return render_template('plan_all.html', shifts=shifts)
        else:
            flash("Access Denied: Only managers can view this page.")
            return redirect(url_for('home'))
    else:
        flash("Please log in to access this page.")
        return redirect(url_for('login'))

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

@app.route('/shift/edit/<int:shift_id>', methods=['GET', 'POST'])
@login_required
def edit_shift(shift_id):
    shift = Shifts.query.get_or_404(shift_id)
    if request.method == 'POST':
        shift.date = request.form.get('date')
        shift.start_time = request.form.get('start_time')
        shift.end_time = request.form.get('end_time')
        if shift.date and shift.start_time and shift.end_time:
            db.session.commit()
            flash("Shift updated successfully!")
            return redirect(url_for('calendar_data_all'))
        else:
            flash("All fields are required!")
    return render_template('edit_shift.html', shift=shift)

@app.route('/shift/delete/<int:shift_id>', methods=['POST'])
@login_required
def delete_shift(shift_id):
    shift = Shifts.query.get_or_404(shift_id)
    db.session.delete(shift)
    db.session.commit()
    flash("Shift deleted successfully!")
    return redirect(url_for('calendar_data_all'))

if __name__ == '__main__':
    app.run(debug=True)