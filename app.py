# app.py
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect,  flash
from flask_restful import Api
from flask_login import (
    LoginManager,
    current_user,
    login_user,
    logout_user,
    login_required,
    UserMixin,
)
from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    ForeignKey,
    Date,
    Time,
    Boolean,
    DateTime,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, aliased

# --- SQLAlchemy setup ---
engine = create_engine("sqlite:///hms.db", echo=True, future=True)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, future=True)


# --- Models ---
class User(Base, UserMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(30), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, index=True)  # admin | doctor | patient
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    admin = relationship("Admin", back_populates="user", uselist=False)
    doctor = relationship("Doctor", back_populates="user", uselist=False)
    patient = relationship("Patient", back_populates="user", uselist=False)


class Admin(Base):
    __tablename__ = "admin"

    id = Column(Integer, primary_key=True)
    uid = Column(Integer, ForeignKey("users.id"), unique=True)

    user = relationship("User", back_populates="admin")
    manages_doctors = relationship("Doctor", back_populates="admin")
    manages_patients = relationship("Patient", back_populates="admin")
    oversees_appointments = relationship("Appointment", back_populates="admin")


class Department(Base):
    __tablename__ = "department"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    doctors = relationship("Doctor", back_populates="department")


class Doctor(Base):
    __tablename__ = "doctor"

    id = Column(Integer, primary_key=True)
    uid = Column(Integer, ForeignKey("users.id"), unique=True)
    depid = Column(Integer, ForeignKey("department.id"))
    license_number = Column(String(50), unique=True, index=True)
    specialization = Column(String(100))
    qualification = Column(Text)
    experience = Column(Integer)
    gender = Column(String(10))
    status = Column(String(20), default="active")
    admin_id = Column(Integer, ForeignKey("admin.id"))

    user = relationship("User", back_populates="doctor")
    department = relationship("Department", back_populates="doctors")
    admin = relationship("Admin", back_populates="manages_doctors")
    appointments = relationship("Appointment", back_populates="doctor")
    availability = relationship("DoctorAvailability", back_populates="doctor")
    treatments = relationship("Treatment", back_populates="doctor")


class Patient(Base):
    __tablename__ = "patient"

    id = Column(Integer, primary_key=True)
    uid = Column(Integer, ForeignKey("users.id"), unique=True)
    gender = Column(String(10))
    dob = Column(Date)
    blood_group = Column(String(5))
    address = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    admin_id = Column(Integer, ForeignKey("admin.id"))

    user = relationship("User", back_populates="patient")
    admin = relationship("Admin", back_populates="manages_patients")
    appointments = relationship("Appointment", back_populates="patient")
    treatments = relationship("Treatment", back_populates="patient")
    medical_history = relationship(
        "MedicalHistory", back_populates="patient", uselist=False
    )


class Appointment(Base):
    __tablename__ = "appointment"

    id = Column(Integer, primary_key=True)
    appointment_number = Column(String(20), unique=True, index=True)
    patid = Column(Integer, ForeignKey("patient.id"))
    docid = Column(Integer, ForeignKey("doctor.id"))
    appoint_date = Column(Date)
    appoint_time = Column(Time)
    status = Column(String(20), default="Booked")  # Booked | Completed | Cancelled
    reason_for_visit = Column(Text)
    admin_id = Column(Integer, ForeignKey("admin.id"))

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    admin = relationship("Admin", back_populates="oversees_appointments")
    treatment = relationship("Treatment", back_populates="appointment", uselist=False)


class Treatment(Base):
    __tablename__ = "treatment"

    id = Column(Integer, primary_key=True)
    appointid = Column(Integer, ForeignKey("appointment.id"))
    docid = Column(Integer, ForeignKey("doctor.id"))
    patid = Column(Integer, ForeignKey("patient.id"))
    diagnosis = Column(Text)
    treatment_plan = Column(Text)
    prescription = Column(Text)
    notes = Column(Text)
    next_visit_date = Column(Date)
    treatment_date = Column(DateTime, default=datetime.utcnow)

    appointment = relationship("Appointment", back_populates="treatment")
    doctor = relationship("Doctor", back_populates="treatments")
    patient = relationship("Patient", back_populates="treatments")


class DoctorAvailability(Base):
    __tablename__ = "doctor_availability"

    id = Column(Integer, primary_key=True)
    docid = Column(Integer, ForeignKey("doctor.id"))
    available_date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)
    available = Column(Boolean, default=True)
    notes = Column(Text)

    doctor = relationship("Doctor", back_populates="availability")


class MedicalHistory(Base):
    __tablename__ = "medical_history"

    id = Column(Integer, primary_key=True)
    patid = Column(Integer, ForeignKey("patient.id"), unique=True)
    allergies = Column(Text)
    chronic_conditions = Column(Text)
    current_medications = Column(Text)
    previous_surgeries = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="medical_history")


# --- Helper functions ---
def calculate_age(dob):
    if not dob:
        return "N/A"
    today = date.today()
    return (
        today.year
        - dob.year
        - ((today.month, today.day) < (dob.month, dob.day))
    )


def create_super_admin():
    session = SessionLocal()
    admin_username = "admin"
    admin_password = "admin123"
    admin_name = "Hospital Admin"

    try:
        existing_admin = session.query(User).filter_by(username=admin_username).first()
        if existing_admin:
            print("[INFO] Admin user already exists.")
            return

        user = User(
            username=admin_username,
            password=generate_password_hash(admin_password),
            name=admin_name,
            role="admin",
        )
        session.add(user)
        session.commit()

        admin = Admin(uid=user.id)
        session.add(admin)
        session.commit()

        print("[SUCCESS] Super admin created:")
        print(f"Username: {admin_username}")
        print(f"Password: {admin_password}")
    except Exception as e:
        session.rollback()
        print(f"[ERROR] create_super_admin: {e}")
    finally:
        session.close()


def create_standard_departments():
    session = SessionLocal()
    standard_departments = [
        {"name": "Cardiology", "description": "Heart and cardiovascular diseases"},
        {"name": "Neurology", "description": "Brain and nervous system disorders"},
        {"name": "Orthopedics","description": "Bones, joints, and musculoskeletal system",},
        {"name": "Pediatrics","description": "Healthcare for children and adolescents",},
        {"name": "Gynecology", "description": "Female reproductive system health"},
        {"name": "Oncology", "description": "Cancer diagnosis and treatment"},
        {"name": "Dermatology", "description": "Skin, hair, and nail conditions"},
        {"name": "Psychiatry", "description": "Mental health and behavioral disorders"},
        {"name": "Radiology", "description": "Medical imaging and diagnosis"},
        {"name": "Emergency Medicine", "description": "Urgent medical care"},
        {"name": "General Surgery", "description": "Surgical procedures and operations"},
        {"name": "Internal Medicine", "description": "Adult diseases and conditions"},
        {"name": "Ophthalmology", "description": "Eye and vision care"},
        {"name": "ENT", "description": "Ear, Nose, and Throat disorders"},
        {"name": "Urology", "description": "Urinary system and male reproductive organs"},
        {"name": "Dentistry", "description": "Oral health and dental care"},
        {"name": "Physiotherapy", "description": "Physical therapy and rehabilitation"},
        {"name": "Nutrition & Dietetics", "description": "Diet and nutritional guidance"},
    ]

    try:
        for dept_data in standard_departments:
            existing_dept = (
                session.query(Department).filter_by(name=dept_data["name"]).first()
            )
            if not existing_dept:
                department = Department(
                    name=dept_data["name"], description=dept_data["description"]
                )
                session.add(department)
        session.commit()
        print("Standard departments created successfully")
    except Exception as e:
        session.rollback()
        print(f"Error creating departments: {e}")
    finally:
        session.close()


# --- Flask app setup ---
app = Flask(__name__)
app.secret_key = "secret_key"

# Initialize Flask-RESTful API
api = Api(app)

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    session = SessionLocal()
    try:
        user = session.get(User, int(user_id))
        if user and user.is_active:
            return user
        return None
    except Exception as e:
        print(f"Error loading user {user_id}: {e}")
        return None
    finally:
        session.close()



@app.context_processor
def inject_user():
    try:
        if current_user.is_authenticated and hasattr(current_user, "name"):
            return dict(current_user=current_user, now=datetime.now())
    except Exception as e:
        print(f"Context processor error: {e}")

    class SafeUser:
        is_authenticated = False
        name = "Guest"
        role = "guest"

    return dict(current_user=SafeUser(), now=datetime.now())



@app.route("/")
def main():
    return render_template("dashboard.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    logout_user()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        session = SessionLocal()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                flash("Logged in successfully.", "success")
                if user.role == "admin":
                    return redirect("/admin/dashboard")
                elif user.role == "doctor":
                    return redirect("/dashboard")
                elif user.role == "patient":
                    return redirect("/dashboard")
                else:
                    flash("Unknown user role.", "danger")
                    logout_user()
                    return redirect("/login") 
            else:
                flash("Invalid username or password.", "danger")
        except Exception as e:
            flash("An error occurred during login.", "danger")
            print(f"Login error: {e}")
        finally:
            session.close()
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        logout_user()

    session = SessionLocal()

    try:
        departments = session.query(Department).order_by(Department.name).all()

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            if not all([name, username, password]):
                flash("Please fill in all required fields.", "danger")
                return render_template("register.html", departments=departments, role="patient")

            existing_user = session.query(User).filter_by(username=username).first()
            if existing_user:
                flash("Username already exists. Please choose another one.", "danger")
                return render_template("register.html", departments=departments, role="patient")

            hashed_password = generate_password_hash(password)
            user = User(
                username=username,
                password=hashed_password,
                name=name,
                role="patient",
            )
            session.add(user)
            session.commit()

            gender = request.form.get("gender")
            dob = request.form.get("dob")
            blood_group = request.form.get("bloodGrp")
            address = request.form.get("address")

            if not all([gender, dob, blood_group, address]):
                flash("Please fill in all patient details.", "danger")
                return render_template("register.html", departments=departments, role="patient")

            new_patient = Patient(
                uid=user.id,
                gender=gender,
                dob=datetime.strptime(dob, "%Y-%m-%d").date(),
                blood_group=blood_group,
                address=address,
                is_active=True
            )
            session.add(new_patient)
            session.commit()

            flash("Patient account created successfully! You can now log in.", "success")
            return redirect("/login")

        return render_template("register.html", departments=departments, role="patient")

    except Exception as e:
        session.rollback()
        print(f"[ERROR] Registration failed: {e}")
        flash("An error occurred during registration. Please try again.", "danger")
        return render_template("register.html", departments=[], role="patient")

    finally:
        session.close()


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect("/login")

@app.route("/dashboard")
@login_required
def m_dash():
    return f"Role: {current_user.role} | Username: {current_user.username}"

            
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        # Get statistics
        total_doctors = session.query(Doctor).count()
        total_patients = session.query(Patient).count()
        total_appointments = session.query(Appointment).count()
        
        # Get recent doctors (last 5)
        doctors = session.query(Doctor).join(User).join(Department).order_by(Doctor.id.desc()).limit(5).all()
        
        # Get recent patients (last 5)
        patients = session.query(Patient).join(User).order_by(Patient.id.desc()).limit(5).all()
        
        # Get recent appointments (last 10)
        appointments = session.query(Appointment).join(Doctor).join(Patient).order_by(Appointment.appoint_date.desc(), Appointment.appoint_time.desc()).limit(10).all()
        
        # Get all departments
        departments = session.query(Department).order_by(Department.name).all()
        
        return render_template("dashboard_admin.html",
                             total_doctors=total_doctors,
                             total_patients=total_patients,
                             total_appointments=total_appointments,
                             doctors=doctors,
                             patients=patients,
                             appointments=appointments,
                             departments=departments)
    except Exception as e:
        print(f"[ERROR] Admin dashboard: {e}")
        flash("Error loading dashboard.", "danger")
        return redirect("/login")
    finally:
        session.close()


@app.route("/doctor/dashboard")
@login_required
def doctor_dashboard():
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")
    return render_template("doctor_dashboard.html")


@app.route("/patient/dashboard")
@login_required
def patient_dashboard():
    if current_user.role != "patient":
        flash("Access denied.", "danger")
        return redirect("/login")
    return render_template("patient_dashboard.html")

@app.route("/admin/addDoctor", methods=["GET", "POST"])
@login_required
def add_doctor():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")

    session = SessionLocal()
    try:
        departments = session.query(Department).order_by(Department.name).all()

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            gender = request.form.get("gender")
            department_id = request.form.get("department")
            license_number = request.form.get("license_number")
            specialization = request.form.get("specialization")
            qualification = request.form.get("qualification")
            experience = request.form.get("experience")

            # Validate inputs
            if not all([name, username, password, gender, department_id, license_number, specialization, qualification]):
                flash("Please fill in all required fields.", "danger")
                return render_template("register.html", departments=departments,role="doctor")

            # Check duplicates
            if qualification<0:
                flash("Qualification cannot be negative", "danger")
                return render_template("register.html", departments=departments,role="doctor")
            existing_user = session.query(User).filter_by(username=username).first()
            existing_license = session.query(Doctor).filter_by(license_number=license_number).first()
            if existing_user:
                flash("Username already exists.", "danger")
                return render_template("register.html", departments=departments,role="doctor")
            if existing_license:
                flash("License number already registered.", "danger")
                return render_template("register.html", departments=departments)

            # Create user
            hashed_password = generate_password_hash(password)
            user = User(username=username, password=hashed_password, name=name, role="doctor")
            session.add(user)
            session.commit()

            # Get the admin safely inside the same session
            admin_record = session.query(Admin).filter_by(uid=current_user.id).first()

            # Create doctor record
            new_doctor = Doctor(
                uid=user.id,
                depid=int(department_id),
                license_number=license_number,
                specialization=specialization,
                qualification=qualification,
                experience=int(experience) if experience else 0,
                gender=gender,
                admin_id=admin_record.id if admin_record else None
            )
            session.add(new_doctor)
            session.commit()

            flash("Doctor added successfully!", "success")
            return redirect("/admin/dashboard")

        return render_template("register.html", departments=departments,role="doctor")
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Add Doctor failed: {e}")
        flash("Error adding doctor. Please try again.", "danger")
        return render_template("register.html", departments=[],role="doctor")
    finally:
        session.close()


@app.route("/admin/doctors")
@login_required
def admin_doctors():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        doctors = session.query(Doctor).join(User).join(Department).order_by(Doctor.id.desc()).all()
        departments = session.query(Department).order_by(Department.name).all()
        return render_template("admin_doctors.html", doctors=doctors, departments=departments)
    except Exception as e:
        print(f"[ERROR] Admin doctors: {e}")
        flash("Error loading doctors.", "danger")
        return redirect("/admin/dashboard")
    finally:
        session.close()


@app.route("/admin/doctor/update/<int:doctor_id>", methods=["POST"])
@login_required
def update_doctor(doctor_id):
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        doctor = session.query(Doctor).filter_by(id=doctor_id).first()
        if not doctor:
            flash("Doctor not found.", "danger")
            return redirect("/admin/doctors")
        
        # Update doctor details
        doctor.specialization = request.form.get("specialization", doctor.specialization)
        doctor.qualification = request.form.get("qualification", doctor.qualification)
        doctor.experience = int(request.form.get("experience", doctor.experience))
        doctor.depid = int(request.form.get("department", doctor.depid))
        
        # Update user name if provided
        if request.form.get("name"):
            doctor.user.name = request.form.get("name")
        
        session.commit()
        flash("Doctor updated successfully!", "success")
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Update doctor: {e}")
        flash("Error updating doctor.", "danger")
    finally:
        session.close()
    
    return redirect("/admin/doctors")


@app.route("/admin/doctor/toggle/<int:doctor_id>/<string:update_status>", methods=["POST"])
@login_required
def toggle_doctor_status(doctor_id, update_status):
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        doctor = session.query(Doctor).filter_by(id=doctor_id).first()
        if not doctor:
            flash("Doctor not found.", "danger")
            return redirect("/admin/doctors")

        # Normalize the input
        update_status = update_status.lower().strip()
        valid_statuses = ["active", "inactive"]
        if update_status not in valid_statuses:
            flash("Invalid status value.", "danger")
            return redirect("/admin/doctors")

        if update_status == "inactive":
            # Deactivate doctor
            if doctor.status == "inactive":
                flash(f"Doctor {doctor.user.name} is already inactive.", "warning")
            else:
                doctor.status = "inactive"
                doctor.user.is_active = False
                flash(f"Doctor {doctor.user.name} has been deactivated.", "warning")

        elif update_status == "active":
            # Activate doctor
            if doctor.status == "active":
                flash(f"Doctor {doctor.user.name} is already active.", "info")
            else:
                doctor.status = "active"
                doctor.user.is_active = True
                flash(f"Doctor {doctor.user.name} has been reactivated.", "success")

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Toggle doctor status: {e}")
        flash("Error updating doctor status.", "danger")
    finally:
        session.close()
    
    return redirect("/admin/doctors")



@app.route("/admin/patients")
@login_required
def admin_patients():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        patients = session.query(Patient).join(User).order_by(Patient.id.desc()).all()
        return render_template("admin_patients.html", patients=patients)
    except Exception as e:
        print(f"[ERROR] Admin patients: {e}")
        flash("Error loading patients.", "danger")
        return redirect("/admin/dashboard")
    finally:
        session.close()


@app.route("/admin/patient/toggle/<int:patient_id>", methods=["POST"])
@login_required
def toggle_patient_status(patient_id):
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        patient = session.query(Patient).filter_by(id=patient_id).first()
        if not patient:
            flash("Patient not found.", "danger")
            return redirect("/admin/patients")
        
        # Toggle status
        patient.is_active = not patient.is_active
        patient.user.is_active = patient.is_active
        
        status_text = "activated" if patient.is_active else "deactivated"
        flash(f"Patient {patient.user.name} has been {status_text}.", "success" if patient.is_active else "warning")
        
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Toggle patient status: {e}")
        flash("Error updating patient status.", "danger")
    finally:
        session.close()
    
    return redirect("/admin/patients")


@app.route("/admin/appointments")
@login_required
def admin_appointments():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        # Get filter parameters
        filter_status = request.args.get("status", "all")
        filter_date = request.args.get("date", "all")
        
        query = session.query(Appointment).join(Doctor).join(Patient)
        
        # Apply status filter
        if filter_status != "all":
            query = query.filter(Appointment.status == filter_status)
        
        # Apply date filter
        today = date.today()
        if filter_date == "upcoming":
            query = query.filter(Appointment.appoint_date >= today)
        elif filter_date == "past":
            query = query.filter(Appointment.appoint_date < today)
        
        appointments = query.order_by(Appointment.appoint_date.desc(), Appointment.appoint_time.desc()).all()
        
        return render_template("admin_appointments.html", 
                             appointments=appointments,
                             filter_status=filter_status,
                             filter_date=filter_date)
    except Exception as e:
        print(f"[ERROR] Admin appointments: {e}")
        flash("Error loading appointments.", "danger")
        return redirect("/admin/dashboard")
    finally:
        session.close()


@app.route("/admin/search", methods=["GET"])
@login_required
def admin_search():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    return render_template("admin_search.html")


@app.route("/admin/search/results", methods=["GET", "POST"])
@login_required
def admin_search_results():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        search_type = request.form.get("search_type") or request.args.get("search_type", "")
        search_term = request.form.get("search_term") or request.args.get("search_term", "")
        
        results = []
        
        if search_type and search_term:
            search_pattern = f"%{search_term}%"
            
            if search_type == "doctor":
                doctors = session.query(Doctor).join(User).join(Department).filter(
                    (User.name.ilike(search_pattern)) |
                    (Doctor.specialization.ilike(search_pattern)) |
                    (Department.name.ilike(search_pattern)) |
                    (Doctor.license_number.ilike(search_pattern))
                ).all()
                
                results = [{
                    "id": d.id,
                    "name": d.user.name,
                    "specialization": d.specialization,
                    "qualification": d.qualification,
                    "experience": d.experience,
                    "status": d.status,
                    "department": d.department.name if d.department else "N/A"
                } for d in doctors]
                
            elif search_type == "patient":
                patients = session.query(Patient).join(User).filter(
                    (User.name.ilike(search_pattern)) |
                    (User.username.ilike(search_pattern)) |
                    (Patient.blood_group.ilike(search_pattern))
                ).all()
                
                results = [{
                    "id": p.id,
                    "patient_id": f"PAT{p.id:06d}",
                    "name": p.user.name,
                    "gender": p.gender,
                    "blood_group": p.blood_group,
                    "contact": p.user.username,
                    "registered_date": p.user.created_at.strftime("%Y-%m-%d") if p.user.created_at else "N/A",
                    "is_active": p.is_active
                } for p in patients]
                
            elif search_type == "appointment":
                appointments = session.query(Appointment).join(Doctor).join(Patient).filter(
                    (Appointment.appointment_number.ilike(search_pattern)) |
                    (User.name.ilike(search_pattern))
                ).all()
                
                results = [{
                    "id": a.id,
                    "appointment_number": a.appointment_number,
                    "patient_name": a.patient.user.name,
                    "doctor_name": a.doctor.user.name,
                    "date": a.appoint_date.strftime("%Y-%m-%d"),
                    "time": a.appoint_time.strftime("%H:%M"),
                    "status": a.status
                } for a in appointments]
        
        return render_template("admin_search_results.html",
                             results=results,
                             search_type=search_type,
                             search_term=search_term)
    except Exception as e:
        print(f"[ERROR] Admin search: {e}")
        flash("Error performing search.", "danger")
        return redirect("/admin/search")
    finally:
        session.close()


@app.route("/admin/departments", methods=["GET"])
@login_required
def admin_departments():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        departments = session.query(Department).order_by(Department.name).all()
        
        # Get doctor count for each department
        dept_stats = []
        for dept in departments:
            doctor_count = session.query(Doctor).filter_by(depid=dept.id).count()
            dept_stats.append({
                "id": dept.id,
                "name": dept.name,
                "description": dept.description,
                "doctor_count": doctor_count,
                "created_at": dept.created_at
            })
        
        return render_template("admin_departments.html", departments=dept_stats)
    except Exception as e:
        print(f"[ERROR] Admin departments: {e}")
        flash("Error loading departments.", "danger")
        return redirect("/admin/dashboard")
    finally:
        session.close()


@app.route("/admin/department/add", methods=["POST"])
@login_required
def add_department():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        
        if not name:
            flash("Department name is required.", "danger")
            return redirect("/admin/departments")
        
        # Check if department already exists
        existing = session.query(Department).filter_by(name=name).first()
        if existing:
            flash("Department already exists.", "danger")
            return redirect("/admin/departments")
        
        new_dept = Department(name=name, description=description)
        session.add(new_dept)
        session.commit()
        
        flash(f"Department '{name}' added successfully!", "success")
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Add department: {e}")
        flash("Error adding department.", "danger")
    finally:
        session.close()
    
    return redirect("/admin/departments")


@app.route("/admin/department/update/<int:dept_id>", methods=["POST"])
@login_required
def update_department(dept_id):
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        dept = session.query(Department).filter_by(id=dept_id).first()
        if not dept:
            flash("Department not found.", "danger")
            return redirect("/admin/departments")
        
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        
        if name:
            dept.name = name
        if description:
            dept.description = description
        
        session.commit()
        flash("Department updated successfully!", "success")
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Update department: {e}")
        flash("Error updating department.", "danger")
    finally:
        session.close()
    
    return redirect("/admin/departments")


@app.route("/admin/reports", methods=["GET"])
@login_required
def admin_reports():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect("/login")
    
    session = SessionLocal()
    try:
        # Get statistics
        total_doctors = session.query(Doctor).count()
        active_doctors = session.query(Doctor).filter_by(status="active").count()
        inactive_doctors = total_doctors - active_doctors
        
        total_patients = session.query(Patient).count()
        active_patients = session.query(Patient).filter_by(is_active=True).count()
        inactive_patients = total_patients - active_patients
        
        total_appointments = session.query(Appointment).count()
        booked_appointments = session.query(Appointment).filter_by(status="Booked").count()
        completed_appointments = session.query(Appointment).filter_by(status="Completed").count()
        cancelled_appointments = session.query(Appointment).filter_by(status="Cancelled").count()
        
        # Department statistics
        departments = session.query(Department).all()
        dept_stats = []
        for dept in departments:
            doctor_count = session.query(Doctor).filter_by(depid=dept.id).count()
            dept_stats.append({
                "name": dept.name,
                "doctor_count": doctor_count
            })
        
        # Recent activity
        recent_doctors = session.query(Doctor).join(User).order_by(User.created_at.desc()).limit(5).all()
        recent_patients = session.query(Patient).join(User).order_by(User.created_at.desc()).limit(5).all()
        recent_appointments = session.query(Appointment).order_by(Appointment.id.desc()).limit(5).all()
        
        return render_template("admin_reports.html",
                             total_doctors=total_doctors,
                             active_doctors=active_doctors,
                             inactive_doctors=inactive_doctors,
                             total_patients=total_patients,
                             active_patients=active_patients,
                             inactive_patients=inactive_patients,
                             total_appointments=total_appointments,
                             booked_appointments=booked_appointments,
                             completed_appointments=completed_appointments,
                             cancelled_appointments=cancelled_appointments,
                             dept_stats=dept_stats,
                             recent_doctors=recent_doctors,
                             recent_patients=recent_patients,
                             recent_appointments=recent_appointments)
    except Exception as e:
        print(f"[ERROR] Admin reports: {e}")
        flash("Error loading reports.", "danger")
        return redirect("/admin/dashboard")
    finally:
        session.close()


# --- Initialization ---
def initialize_app():
    Base.metadata.create_all(engine)
    create_super_admin()
    create_standard_departments()


if __name__ == "__main__":
    initialize_app()
    app.run(debug=True)
