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

app.logger.setLevel(logging.DEBUG)  # Set logging level to DEBUG

# Add a StreamHandler to output logs to the console
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)

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
    shifts = db.relationship('Shifts', backref='user', lazy=True)
    skill = db.Column(db.String(200), nullable=True)

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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    skill = db.Column(db.String(100), nullable=False)  

    def __repr__(self):
        return '<Shift %r>' % self.id
    
class TimeOffRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200))
    status = db.Column(db.String(20), default='Pending')

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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    work_on_weekends = db.Column(db.Boolean, default=False)
    employees = db.relationship('Users', backref='company', lazy=True)

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
                role=form.role.data,
                skill=form.skill.data
            )
            db.session.add(user)  
            db.session.commit()  
            flash("User Added Successfully")
            return redirect(url_for('login')) 

    return render_template("register.html", form=form, name=name)

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
    if current_user.role == 'manager':
        company = Company.query.filter_by(manager_id=current_user.id).first()
        if request.method == 'POST':
            company_name = request.form.get('company_name')
            work_on_weekends = request.form.get('work_on_weekends') == 'on'
            if company_name:
                new_company = Company(
                    name=company_name,
                    manager_id=current_user.id,
                    work_on_weekends=work_on_weekends
                )
                db.session.add(new_company)
                db.session.commit()
                flash("Company created successfully!")
                return redirect(url_for('dashboard'))
    elif current_user.role == 'employee':
        company = current_user.company
    return render_template('dashboard.html', company=company)

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
    return render_template('requests.html', requests=requests)

@app.route('/view_time_off_request', methods=['GET', 'POST'])
@login_required
def view_time_off_request():
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

        # Ensure all required fields are provided
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

        # Fetch the skill of the selected user
        user = Users.query.get(user_id)
        if not user:
            flash("Selected user does not exist.")
            return redirect(url_for('add_shift'))

        # Add the new shift with the user's skill
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

    print("Employees:", [(emp.id, emp.name, emp.skill) for emp in employees])
    print("Shift Templates:", [(t.day_type, t.start_time, t.end_time, t.skill, t.required_employees) for t in shift_templates])
    print("Day Overrides:", [(o.day, o.start_time, o.end_time, o.skill, o.required_employees) for o in day_overrides])

    employee_ids = [emp.id for emp in employees]
    employee_skills = {emp.id: emp.skill for emp in employees}

    # Prepare shifts_needed dictionary
    shifts_needed = {"weekday": {}, "weekend": {}}

    # Map short day names (e.g., "Mon") to full day names (e.g., "Monday")
    day_name_map = {
        "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
        "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"
    }

    # Add shift templates to shifts_needed
    for template in shift_templates:
        if template.day_type == "Weekday":
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
                key = (day, template.start_time, template.end_time, template.skill)
                shifts_needed["weekday"][key] = template.required_employees
        elif works_on_weekends and template.day_type == "Weekend":
            for day in ["Saturday", "Sunday"]:
                key = (day, template.start_time, template.end_time, template.skill)
                shifts_needed["weekend"][key] = template.required_employees

    print("Shifts Needed Before Overrides:", shifts_needed)

    # Apply day-specific overrides
    for override in day_overrides:
        full_day_name = day_name_map.get(override.day, override.day)  # Convert short day name to full day name
        override_key = (full_day_name, override.start_time, override.end_time, override.skill)
        if full_day_name in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            # Adjust the weekday shifts for the specific day
            if override_key in shifts_needed["weekday"]:
                shifts_needed["weekday"][override_key] += override.required_employees
            else:
                shifts_needed["weekday"][override_key] = override.required_employees
        elif works_on_weekends and full_day_name in ["Saturday", "Sunday"]:
            # Adjust the weekend shifts for the specific day
            if override_key in shifts_needed["weekend"]:
                shifts_needed["weekend"][override_key] += override.required_employees
            else:
                shifts_needed["weekend"][override_key] = override.required_employees

    print("Shifts Needed After Overrides:", shifts_needed)

    # Define decision variables
    employee_shifts = {}
    for emp_id in employee_ids:
        for (day_name, start_time, end_time, skill) in shifts_needed["weekday"]:
            employee_shifts[(emp_id, day_name, start_time, end_time, skill)] = model.NewBoolVar(
                f"emp_{emp_id}_day_{day_name}_{start_time}_{end_time}_{skill}"
            )

    # Add constraints
    for (day_name, start_time, end_time, skill), num_employees in shifts_needed["weekday"].items():
        constraint = model.Add(
            sum(
                employee_shifts[(emp_id, day_name, start_time, end_time, skill)]
                for emp_id in employee_ids
                if employee_skills[emp_id] == skill
            )
            >= num_employees
        )
        print(f"Added staffing constraint for {day_name}, {start_time}-{end_time}, Skill: {skill}, Required: {num_employees}")

    if works_on_weekends:
        for (day_name, start_time, end_time, skill), num_employees in shifts_needed["weekend"].items():
            constraint = model.Add(
                sum(
                    employee_shifts[(emp_id, day_name, start_time, end_time, skill)]
                    for emp_id in employee_ids
                    if employee_skills[emp_id] == skill
                )
                >= num_employees
            )
            print(f"Added weekend staffing constraint for {day_name}, {start_time}-{end_time}, Skill: {skill}, Required: {num_employees}")

    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL:
        print("Solution Found: OPTIMAL")
    elif status == cp_model.FEASIBLE:
        print("Solution Found: FEASIBLE")
    elif status == cp_model.INFEASIBLE:
        print("No Solution: INFEASIBLE")
    elif status == cp_model.MODEL_INVALID:
        print("Model Invalid")
    else:
        print("Unknown Solver Status")

    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        schedule = {}
        for emp_id in employee_ids:
            for (day_name, start_time, end_time, skill) in shifts_needed["weekday"]:
                if solver.Value(employee_shifts[(emp_id, day_name, start_time, end_time, skill)]) == 1:
                    if (day_name, start_time, skill) not in schedule:
                        schedule[(day_name, start_time, skill)] = []
                    schedule[(day_name, start_time, skill)].append(emp_id)
                    print(f"Assigned Employee {emp_id} to {day_name}, {start_time}-{end_time}, Skill: {skill}")
        return schedule
    else:
        return None
    
@app.route('/generate_schedule', methods=['GET', 'POST'])
@login_required
def generate_schedule_route():
    if current_user.role != 'manager': 
        flash("Access Denied: Only managers can generate schedules.")
        return redirect(url_for('home'))

    # Fetch company configuration
    config = CompanyConfig.query.first()
    works_on_weekends = config.works_on_weekends if config else False

    # Generate the schedule
    schedule = generate_schedule(works_on_weekends)

    if not schedule:
        flash("No feasible schedule could be generated. Please adjust the constraints or input data.", "error")
        return redirect('/view_schedule')

    # Debugging: Print the generated schedule
    print("Generated Schedule:", schedule)

    # Save the schedule to the database
    today = datetime.now()
    for (day, start_time, skill), employee_ids in schedule.items():
        for emp_id in employee_ids:
            # Retrieve the end_time from the ShiftTemplate
            end_time = None
            for template in ShiftTemplate.query.all():
                if template.start_time.strftime('%H:%M') == start_time and template.skill == skill:
                    end_time = template.end_time.strftime('%H:%M')
                    break

            if not end_time:
                flash(f"End time not found for start_time={start_time}, skill={skill}.", "error")
                return redirect('/view_schedule')

            # Calculate the shift date
            shift_date = today + timedelta(days=day)

            # Debugging: Print the shift being added
            print(f"Adding Shift: Date={shift_date.strftime('%Y-%m-%d')}, Day={day}, Start={start_time}, End={end_time}, User ID={emp_id}")

            # Add the shift to the database
            shift = Shifts(
                date=shift_date.strftime('%Y-%m-%d'),
                day=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day],
                start_time=start_time,
                end_time=end_time,
                user_id=emp_id
            )
            db.session.add(shift)

    # Commit the changes to the database
    try:
        db.session.commit()
        flash("Schedule successfully generated!", "success")
    except Exception as e:
        db.session.rollback()
        print("Error saving schedule to database:", e)
        flash("An error occurred while saving the schedule. Please try again.", "error")

    return redirect('/view_schedule')

@app.route('/view_schedule')
def view_schedule():
    if current_user.role != 'manager': 
        flash("Access Denied: Only managers can view schedule.")
        return redirect(url_for('home'))
    shifts = Shifts.query.options(joinedload(Shifts.user)).all()
    print("Shifts:", shifts)  
    return render_template('schedule.html', shifts=shifts)

if __name__ == '__main__':
    app.run(debug=True)
