from flask import Flask, render_template, logging
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from flask import request, flash, redirect, url_for, session
from webforms import LoginForm, UserForm
from datetime import datetime, timedelta
from ortools.sat.python import cp_model
from sqlalchemy.orm import joinedload
from datetime import date
import logging
import sys

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = "samo levski"

db = SQLAlchemy()
db.init_app(app)

class Users(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False, default='employee')
    skill = db.Column(db.String(200), nullable=True)
    
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)  # Explicit Foreign Key

    company = db.relationship('Company', backref='employees', foreign_keys=[company_id])  # Explicitly set FK



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
    __tablename__ = 'shifts'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(20), nullable=False)
    end_time = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Foreign key to Users
    skill = db.Column(db.String(100), nullable=False)

    # Define relationship to Users
    user = db.relationship('Users', backref='shifts', foreign_keys=[user_id])

    
class TimeOffRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200))
    status = db.Column(db.String(20), default='Pending')
    
    # Relationship to Users model
    user = db.relationship('Users', backref='time_off_requests')


class ShiftTemplate(db.Model):
    __tablename__ = 'shift_template'
    id = db.Column(db.Integer, primary_key=True)
    day_type = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    skill = db.Column(db.String(100), nullable=False)  
    required_employees = db.Column(db.Integer, nullable=False)

class DaySpecificOverride(db.Model):
    __tablename__ = 'day_specific_override'
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    skill = db.Column(db.String(100), nullable=False)  
    required_employees = db.Column(db.Integer, nullable=False)

class CompanyConfig(db.Model):
    __tablename__ = 'company_config'
    id = db.Column(db.Integer, primary_key=True)
    works_on_weekends = db.Column(db.Boolean, nullable=False, default=False)

class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    manager = db.relationship('Users', backref='managed_company', foreign_keys=[manager_id])


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
            print(f"User found: {user}")  # Debugging: Print user details
            if check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                flash("Login Successful")
                session['username'] = username
                print("Login successful, redirecting to dashboard.")  # Debugging
                return redirect(url_for('dashboard'))
            else:
                flash("Wrong Password - Try Again")
                print("Wrong password.")  # Debugging
        else:
            flash("User Not Found - Try Again")
            print("User not found.")  # Debugging
    else:
        print("Form validation failed.")  # Debugging
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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')
        skill = request.form.get('skill')

        # Validate form inputs
        if not username or not email or not password or not confirm_password or not role:
            flash("All fields are required!")
            return redirect(url_for('register'))

        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect(url_for('register'))

        # Check if the username or email already exists
        existing_user = Users.query.filter((Users.username == username) | (Users.email == email)).first()
        if existing_user:
            flash("Username or email already exists!")
            return redirect(url_for('register'))

        # Create a new user
        hashed_password = generate_password_hash(password)
        new_user = Users(
            username=username,
            email=email,
            password_hash=hashed_password,
            role=role,
            skill=skill,
            name=username  # Default name to username
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))

    return render_template("register.html")

@app.route('/set_company_policy', methods=['GET', 'POST'])
def set_company_policy():
    if request.method == 'POST':
        works_on_weekends = request.form.get('works_on_weekends') == 'on'

        config = CompanyConfig.query.first()
        if config:
            config.works_on_weekends = works_on_weekends
        else:
            config = CompanyConfig(works_on_weekends=works_on_weekends)
            db.session.add(config)
        
        db.session.commit()
        flash("Company policy updated successfully!")
        return redirect(url_for('set_company_policy'))

    config = CompanyConfig.query.first()
    return render_template('set_company_policy.html', config=config)


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    company = None
    employees = []

    if current_user.role == 'manager':
        company = Company.query.filter_by(manager_id=current_user.id).first()

        if request.method == 'POST':
            # First, check if the manager is trying to create a company
            company_name = request.form.get('company_name')
            if company_name and not company:
                company = Company(name=company_name, manager_id=current_user.id)
                db.session.add(company)
                db.session.commit()
                flash(f"Company '{company_name}' created successfully!", "success")
                return redirect(url_for('dashboard'))  # Refresh page

            # If the manager is assigning an employee to the company
            employee_id = request.form.get('employee_id')
            if employee_id and company:
                employee = Users.query.get(employee_id)
                if employee:
                    employee.company_id = company.id
                    db.session.commit()
                    flash(f"{employee.name} has been added to {company.name}!", "success")
                else:
                    flash("Invalid employee selected.", "danger")
            elif employee_id and not company:
                flash("Please create a company first before assigning employees.", "danger")

        employees = Users.query.filter_by(company_id=None, role='employee').all()

    elif current_user.role == 'employee':
        company = Company.query.get(current_user.company_id)

    return render_template('dashboard.html', company=company, employees=employees)


@app.route('/requests_employee', methods=['GET', 'POST'])
@login_required
def requests_employee():
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason')

        if start_date and end_date and reason:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

                new_request = TimeOffRequest(
                    user_id=current_user.id,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason
                )

                db.session.add(new_request)
                db.session.commit()
                flash("Request submitted successfully!")
            except ValueError:
                flash("Invalid date format. Please use YYYY-MM-DD.")
        else:
            flash("All fields are required!")

    requests = TimeOffRequest.query.filter_by(user_id=current_user.id).all()
    return render_template('requests_employee.html', requests=requests)


@app.route('/requests', methods=['GET'])
@login_required
def requests():
    if current_user.role != 'manager':
        flash("You are not authorized to view this page.")
        return redirect(url_for('dashboard'))

    requests = TimeOffRequest.query.options(db.joinedload(TimeOffRequest.user)).all()  # Load user details

    return render_template('requests.html', requests=requests)




@app.route('/view_time_off_request', methods=['GET', 'POST'])
@login_required
def view_time_off_request():
    if current_user.role != 'manager':
        flash("You are not authorized to view this page.")
        return redirect(url_for('dashboard'))  

    if request.method == 'POST':
        request_id = request.form.get('request_id')
        action = request.form.get('action')
        time_off_request = TimeOffRequest.query.get(request_id)

        if time_off_request:
            if action == 'approve':
                time_off_request.status = 'Approved'
            elif action == 'reject':
                time_off_request.status = 'Rejected'
            db.session.commit()
            flash(f"Request {action}d successfully!")
        else:
            flash("Invalid request ID.")

    return redirect(url_for('requests'))



@app.route('/')
def home():
    return render_template('startingpage.html')

#app.logger.setLevel(logging.DEBUG)

#@app.route('/h')
#def home():
    #app.logger.debug('This is a debug message')  # Test logging
    #return "Hello, World!"

@app.route('/home')
@login_required
def home2():
    if current_user.role == 'manager':
        return render_template('add_shift.html')
    else:
        return render_template('home.html')


@app.route('/calendar-data', methods=['GET'])
@login_required
def calendar_data():
    if current_user.role != 'employee':
        flash("Access Denied: Only employees can view this page.")
        return redirect(url_for('dashboard'))
    
    if current_user.company:
        shifts = Shifts.query.join(Users).filter(Users.company_id == current_user.company.id).all()
    else:
        shifts = Shifts.query.filter_by(user_id=current_user.id).all()

    for shift in shifts:
        shift.date = shift.date  

    today = datetime.now()
    calendar_days = [today + timedelta(days=i) for i in range(7)] 
    return render_template('calendar_data.html', shifts=shifts, calendar_days=calendar_days)

@app.route('/shift/add', methods=['GET', 'POST'])
@login_required
def add_shift():
    if current_user.role != 'manager':
        flash("Access Denied: Only managers can add shifts.")
        return redirect(url_for('home'))
    if request.method == 'POST':
        shift_id = request.form.get('shift_id')
        date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        user_id = request.form.get('user_id')
        day = datetime.strptime(date, '%Y-%m-%d').strftime('%A') if date else None

        if not date or not start_time or not end_time or not user_id:
            flash("All fields are required!")
            return redirect(url_for('add_shift'))

        shift_year = datetime.strptime(date, '%Y-%m-%d').year
        if shift_year != 2025:
            flash("The year must be 2025.")
            return redirect(url_for('add_shift'))

        if start_time >= end_time:
            flash("Start time must be earlier than end time.")
            return redirect(url_for('add_shift'))

        if shift_id:
            old_shift = Shifts.query.get(shift_id)
            if old_shift:
                db.session.delete(old_shift)
                db.session.commit()

        overlapping_shifts = Shifts.query.filter(
            Shifts.user_id == user_id,
            Shifts.date == date,
            db.or_(
                db.and_(Shifts.start_time <= start_time, Shifts.end_time > start_time),
                db.and_(Shifts.start_time < end_time, Shifts.end_time >= end_time),
                db.and_(Shifts.start_time >= start_time, Shifts.end_time <= end_time)
            )
        ).all()

        if overlapping_shifts:
            flash("Shift overlaps with an existing shift for this employee.")
            return redirect(url_for('add_shift'))

        user = Users.query.get(user_id)
        if not user:
            flash("Selected user does not exist.")
            return redirect(url_for('add_shift'))

        new_shift = Shifts(date=date, start_time=start_time, end_time=end_time, user_id=user_id, day=day, skill=user.skill)
        db.session.add(new_shift)
        db.session.commit()

        flash("Shift updated successfully!" if shift_id else "Shift added successfully!")
        return redirect(url_for('add_shift'))

    users = Users.query.all()
    shifts = Shifts.query.all()

    today = datetime.now()
    calendar_days = [today + timedelta(days=i) for i in range(7)]
    return render_template('add_shift.html', users=users, shifts=shifts, calendar_days=calendar_days)

@app.route('/shift/delete/<int:shift_id>', methods=['POST'])
@login_required
def delete_shift(shift_id):
    if current_user.role != 'manager':
        flash("Access Denied: Only managers can delete shifts.")
        return redirect(url_for('home'))
    shift = Shifts.query.get_or_404(shift_id)
    db.session.delete(shift)
    db.session.commit()
    flash("Shift deleted successfully!")
    return redirect(url_for('add_shift'))

@app.route('/view_shift_templates')
def view_shift_templates():
    if current_user.role != 'manager': 
        flash("Access Denied: Only managers can set shift templates.")
        return redirect(url_for('home'))
    shift_templates = ShiftTemplate.query.all()
    return render_template('view_shift_templates.html', shift_templates=shift_templates)


@app.route('/set_shift_template', methods=['GET', 'POST'])
def set_shift_template():
    if current_user.role != 'manager': 
        flash("Access Denied: Only managers can set shift templates.")
        return redirect(url_for('home'))
    if request.method == 'POST':
        day_type = request.form['day_type']
        start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
        end_time = datetime.strptime(request.form['end_time'], '%H:%M').time()
        skill = request.form['skill']
        required_employees = int(request.form['required_employees'])

        new_template = ShiftTemplate(
            day_type=day_type,
            start_time=start_time,
            end_time=end_time,
            skill=skill, 
            required_employees=required_employees
        )
        db.session.add(new_template)
        db.session.commit()
        flash("Shift template updated successfully!")
        return redirect(url_for('view_shift_templates'))

    return render_template('set_shift_template.html')

@app.route('/view_day_overrides')
def view_day_overrides():
    if current_user.role != 'manager': 
        flash("Access Denied: Only managers can set day overrides.")
        return redirect(url_for('home'))
    day_overrides = DaySpecificOverride.query.all()
    return render_template('view_day_overrides.html', day_overrides=day_overrides)

@app.route('/set_day_override', methods=['GET', 'POST'])
def set_day_override():
    if current_user.role != 'manager': 
        flash("Access Denied: Only managers can set day overrides.")
        return redirect(url_for('home'))
    if request.method == 'POST':
        day = request.form['day']
        start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
        end_time = datetime.strptime(request.form['end_time'], '%H:%M').time()
        skill = request.form['skill']  
        required_employees = int(request.form['required_employees'])

        new_override = DaySpecificOverride(
            day=day,
            start_time=start_time,
            end_time=end_time,
            skill=skill,  
            required_employees=required_employees
        )
        db.session.add(new_override)
        db.session.commit()
        flash("Day-specific override added successfully!")
        return redirect(url_for('view_day_overrides'))

    return render_template('set_day_override.html')



def fetch_scheduling_data():
    employees = Users.query.filter_by(role='employee').all()

    shift_templates = ShiftTemplate.query.all()

    overrides = DaySpecificOverride.query.all()

    return employees, shift_templates, overrides

def build_weekly_requirements(works_on_weekends):
    employees, templates, overrides = fetch_scheduling_data()

    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    if works_on_weekends:
        days_of_week.extend(['Saturday', 'Sunday'])

    weekly_requirements = []

    for day in days_of_week:
        for template in templates:
            if template.day_type == 'weekend' and day in ['Saturday', 'Sunday']:
                weekly_requirements.append({
                    'day': day,
                    'start_time': template.start_time,
                    'end_time': template.end_time,
                    'employees': template.employees,
                    'skill_required': template.skill_required
                })
            elif template.day_type == 'weekday' and day not in ['Saturday', 'Sunday']:
                weekly_requirements.append({
                    'day': day,
                    'start_time': template.start_time,
                    'end_time': template.end_time,
                    'employees': template.employees,
                    'skill_required': template.skill_required
                })

        for override in overrides:
            if override.day == day:
                weekly_requirements.append({
                    'day': day,
                    'start_time': override.start_time,
                    'end_time': override.end_time,
                    'employees': override.employees,
                    'skill_required': override.skill_required
                })

    return weekly_requirements, employees

def generate_schedule(works_on_weekends):
    model = cp_model.CpModel()

    # Fetch data from the database
    employees = Users.query.filter_by(role="employee").all()
    shift_templates = ShiftTemplate.query.all()
    day_overrides = DaySpecificOverride.query.all()
    approved_time_offs = TimeOffRequest.query.filter_by(status="Approved").all()

    # Debugging: Log input data
    print("Employees:", [(emp.id, emp.username, emp.skill) for emp in employees])
    print("Shift Templates:", [(t.day_type, t.start_time, t.end_time, t.skill, t.required_employees) for t in shift_templates])
    print("Day Overrides:", [(o.day, o.start_time, o.end_time, o.skill, o.required_employees) for o in day_overrides])

    # Map abbreviated day names to full day names
    day_name_map = {
        "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
        "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"
    }

    # Create a mapping from full day names to dates
    today = datetime.now()
    day_to_date = {
        full_day: (today + timedelta(days=i)).date()
        for i, full_day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
    }

    # Initialize employee data
    employee_ids = [emp.id for emp in employees]
    employee_skills = {emp.id: emp.skill for emp in employees}

    # Map approved time-off requests
    time_off_map = {emp.id: [] for emp in employees}
    for request in approved_time_offs:
        time_off_map[request.user_id].append((request.start_date, request.end_date))

    # Build shifts needed based on templates and overrides
    shifts_needed = {}
    for template in shift_templates:
        day_range = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"] if template.day_type == "Weekday" else ["Saturday", "Sunday"]
        for day in day_range:
            if template.day_type == "Weekend" and not works_on_weekends:
                continue
            key = (day, template.start_time, template.end_time, template.skill)
            shifts_needed[key] = template.required_employees

    for override in day_overrides:
        # Normalize day names
        full_day_name = day_name_map.get(override.day, override.day)
        key = (full_day_name, override.start_time, override.end_time, override.skill)
        shifts_needed[key] = override.required_employees

    # Debugging: Log shifts needed
    print("Shifts Needed After Overrides:", shifts_needed)

    # Create variables and constraints
    employee_shifts = {}
    for emp_id in employee_ids:
        for (day, start_time, end_time, skill), required_employees in shifts_needed.items():
            if employee_skills[emp_id] != skill:
                continue
            if any(start_date <= day_to_date[day] <= end_date for start_date, end_date in time_off_map[emp_id]):
                continue
            employee_shifts[(emp_id, day, start_time, end_time, skill)] = model.NewBoolVar(
                f"emp_{emp_id}_{day}_{start_time}_{end_time}_{skill}"
            )

    # Add staffing constraints
    for (day, start_time, end_time, skill), required_employees in shifts_needed.items():
        eligible_employees = [
            emp_id for emp_id in employee_ids
            if (emp_id, day, start_time, end_time, skill) in employee_shifts
        ]
        if len(eligible_employees) < required_employees:
            print(f"Not enough eligible employees for {day}, {start_time}-{end_time}, Skill: {skill}")
            continue
        model.Add(
            sum(employee_shifts[(emp_id, day, start_time, end_time, skill)] for emp_id in eligible_employees) >= required_employees
        )
        print(f"Added staffing constraint for {day}, {start_time}-{end_time}, Skill: {skill}, Required: {required_employees}")

    # Add fairness constraints (optional)
    total_shifts = {emp_id: model.NewIntVar(0, len(shifts_needed), f"total_shifts_{emp_id}") for emp_id in employee_ids}
    for emp_id in employee_ids:
        model.Add(
            total_shifts[emp_id] == sum(
                employee_shifts[(emp_id, day, start_time, end_time, skill)]
                for (day, start_time, end_time, skill) in shifts_needed
                if (emp_id, day, start_time, end_time, skill) in employee_shifts
            )
        )
    max_shifts = model.NewIntVar(0, len(shifts_needed), "max_shifts")
    min_shifts = model.NewIntVar(0, len(shifts_needed), "min_shifts")
    model.AddMaxEquality(max_shifts, [total_shifts[emp_id] for emp_id in employee_ids])
    model.AddMinEquality(min_shifts, [total_shifts[emp_id] for emp_id in employee_ids])
    model.Add(max_shifts - min_shifts <= 1)

    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        print("Solution Found")
        schedule = {}
        for emp_id in employee_ids:
            for (day, start_time, end_time, skill), _ in shifts_needed.items():
                if (emp_id, day, start_time, end_time, skill) in employee_shifts and solver.Value(employee_shifts[(emp_id, day, start_time, end_time, skill)]) == 1:
                    date = day_to_date[day]
                    schedule.setdefault((date, day, start_time, end_time, skill), []).append(emp_id)
        return schedule
    else:
        print(f"Solver failed with status: {solver.StatusName(status)}")
        return None


    
@app.route('/generate_schedule', methods=['GET', 'POST'])
@login_required
def generate_schedule_route():
    if current_user.role != 'manager': 
        flash("Access Denied: Only managers can generate schedules.")
        return redirect(url_for('home'))

    config = CompanyConfig.query.first()
    works_on_weekends = config.works_on_weekends if config else False

    schedule = generate_schedule(works_on_weekends)

    if not schedule:
        flash("No feasible schedule could be generated.", "error")
        print("No feasible schedule could be generated.")  # Debugging
        return redirect('/view_schedule')

    print("Generated Schedule:", schedule)  # Debugging

    try:
        for (date, day, start_time, end_time, skill), employee_ids in schedule.items():
            for emp_id in employee_ids:
                # Format `start_time` and `end_time` as strings
                if isinstance(start_time, datetime.time):
                    start_time_str = start_time.strftime('%H:%M')
                elif isinstance(start_time, str):  # If already a string, use as-is
                    start_time_str = start_time
                else:
                    raise ValueError(f"Invalid start_time type: {type(start_time)}")

                if isinstance(end_time, datetime.time):
                    end_time_str = end_time.strftime('%H:%M')
                elif isinstance(end_time, str):  # If already a string, use as-is
                    end_time_str = end_time
                else:
                    raise ValueError(f"Invalid end_time type: {type(end_time)}")

                # Format `date` as a string
                if isinstance(date, datetime.date):
                    date_str = date.strftime('%Y-%m-%d')
                elif isinstance(date, str):  # If already a string, use as-is
                    date_str = date
                else:
                    raise ValueError(f"Invalid date type: {type(date)}")

                # Add the shift to the database
                shift = Shifts(
                    date=date_str,  # Use formatted date
                    day=day,
                    start_time=start_time_str,  # Use formatted start_time
                    end_time=end_time_str,  # Use formatted end_time
                    user_id=emp_id,
                    skill=skill
                )
                db.session.add(shift)
                print(f"Added shift: {shift}")  # Debugging

        # Commit the changes to the database
        db.session.commit()
        flash("Schedule successfully generated!", "success")
        print("Schedule successfully saved to the database.")  # Debugging
    except Exception as e:
        db.session.rollback()
        flash("An error occurred while saving the schedule.", "error")
        print(f"Error saving schedule to database: {e}")  # Debugging

    return redirect('/view_schedule')

@app.route('/view_schedule')
@login_required
def view_schedule():
    if current_user.role != 'manager': 
        flash("Access Denied: Only managers can view schedule.")
        return redirect(url_for('home'))
    shifts = Shifts.query.options(joinedload(Shifts.user)).all()
    print("Shifts:", shifts)  
    return render_template('schedule.html', shifts=shifts)

if __name__ == '__main__':
    app.run(debug=True)
