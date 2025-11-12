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
    func
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, aliased
from datetime import date, timedelta


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

def mark_complete(appointment_id):
    session = SessionLocal()
    try:
        appointment = session.query(Appointment).filter_by(id=appointment_id).first()
        if not appointment:
            flash("Appointment not found.", "warning")
            return redirect("/doctor/appointments")

        appointment.status = "Completed"
        session.commit()
        flash(f"Appointment #{appointment.appointment_number} marked as completed.", "success")
        return redirect("/doctor/appointments")
    except Exception as e:
        print("[ERROR] doctor_mark_complete:", e)
        flash("Error updating appointment.", "danger")
        session.rollback()
        return redirect("/doctor/appointments")
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

    session = SessionLocal()
    try:
        doctor = session.query(Doctor).filter_by(uid=current_user.id).first()
        if not doctor:
            flash("Doctor profile not found.", "danger")
            return redirect("/login")

        today = date.today()
        next_week = today + timedelta(days=7)

        todays_appointments = (
            session.query(Appointment)
            .filter(Appointment.docid == doctor.id, Appointment.appoint_date == today)
            .count()
        )

        pending_consultations = (
            session.query(Appointment)
            .filter(Appointment.docid == doctor.id, Appointment.status == "Booked")
            .count()
        )

        upcoming_appointments = (
            session.query(Appointment)
            .filter(Appointment.docid == doctor.id, Appointment.appoint_date.between(today, next_week))
            .count()
        )

        assigned_patients = (
            session.query(Patient)
            .join(Appointment, Appointment.patid == Patient.id)
            .filter(Appointment.docid == doctor.id)
            .group_by(Patient.id)
            .order_by(func.max(Appointment.appoint_date).desc())
            .limit(5)
            .all()
        )

        chart_start = today - timedelta(days=6)
        daily_counts = (
            session.query(Appointment.appoint_date, func.count(Appointment.id))
            .filter(Appointment.docid == doctor.id, Appointment.appoint_date >= chart_start)
            .group_by(Appointment.appoint_date)
            .order_by(Appointment.appoint_date)
            .all()
        )

        chart_data = {
            "dates": [str(d[0]) for d in daily_counts],
            "counts": [d[1] for d in daily_counts],
        }

        return render_template(
            "dashboard_doctor.html",
            todays_appointments=todays_appointments,
            pending_consultations=pending_consultations,
            upcoming_appointments=upcoming_appointments,
            assigned_patients=assigned_patients,
            chart_data=chart_data,
        )

    except Exception as e:
        import traceback
        print("[ERROR] Doctor dashboard:", e)
        traceback.print_exc()
        flash("Error loading dashboard.", "danger")
        return redirect("/login")
    finally:
        session.close()


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

@app.route("/doctor/appointments")
@login_required
def doctor_appointments():
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")

    session = SessionLocal()
    try:
        doctor = session.query(Doctor).filter_by(uid=current_user.id).first()
        if not doctor:
            flash("Doctor profile not found.", "danger")
            return redirect("/login")

        today = date.today()
        next_week = today + timedelta(days=7)

        filter_option = request.args.get("filter", "all")

        query = session.query(Appointment).join(Patient, Appointment.patid == Patient.id).filter(Appointment.docid == doctor.id)

        if filter_option == "today":
            query = query.filter(Appointment.appoint_date == today)
        elif filter_option == "upcoming":
            query = query.filter(Appointment.appoint_date.between(today, next_week))

        appointments_query = query.order_by(Appointment.appoint_date.asc(), Appointment.appoint_time.asc()).all()


        appointments = []
        for appt in appointments_query:
            patient = appt.patient
            user = patient.user

            age = 0
            if patient.dob:
                today_date = date.today()
                age = today_date.year - patient.dob.year - (
                    (today_date.month, today_date.day) < (patient.dob.month, patient.dob.day)
                )

            appointments.append({
                "id": appt.id,
                "appointment_number": appt.appointment_number,
                "appointment_date": str(appt.appoint_date),
                "appointment_time": str(appt.appoint_time),
                "status": appt.status,
                "reason": appt.reason_for_visit,
                "patient_name": user.name if user else "Unknown",
                "patient_gender": patient.gender or "-",
                "patient_age": age,
                "patient_blood_group": patient.blood_group or "-",
                "patient_address": patient.address or "-",
            })

        total_appointments = len(appointments)
        todays_appointments = sum(1 for a in appointments if a["appointment_date"] == str(today))
        upcoming_appointments = sum(
            1 for a in appointments
            if str(today) <= a["appointment_date"] <= str(next_week) and a["status"] == "Booked"
        )

        return render_template(
            "doctor_appointments.html",
            appointments=appointments,
            total_appointments=total_appointments,
            todays_appointments=todays_appointments,
            upcoming_appointments=upcoming_appointments,
        )

    except Exception as e:
        print("[ERROR] doctor_appointments:", e)
        flash("Error loading appointments.", "danger")
        return redirect("/doctor/dashboard")  
    finally:
        session.close()


@app.route("/doctor/appointment/view/<int:appointment_id>")
@login_required
def doctor_view_appointment(appointment_id):
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")

    session = SessionLocal()
    try:
        appointment = (
            session.query(Appointment)
            .filter_by(id=appointment_id)
            .first()
        )

        if not appointment:
            flash("Appointment not found.", "danger")
            return redirect("/doctor/appointments")

        patient = session.query(Patient).filter_by(id=appointment.patid).first()
        user = session.query(User).filter_by(id=patient.uid).first() if patient else None

        treatment = session.query(Treatment).filter_by(appointid=appointment.id).first()

        return render_template(
            "doctor_view_appointment.html",
            appointment=appointment,
            patient=patient,
            user=user,
            treatment=treatment,
        )

    except Exception as e:
        print("[ERROR] doctor_view_appointment:", e)
        flash("Error loading appointment details.", "danger")
        return redirect("/doctor/appointments")
    finally:
        session.close()



@app.route("/doctor/mark/complete/<int:appointment_id>")
@login_required
def doctor_mark_complete(appointment_id):
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")
    mark_complete(appointment_id)


@app.route("/doctor/mark/cancel/<int:appointment_id>")
@login_required
def doctor_mark_cancel(appointment_id):
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")
    session = SessionLocal()
    try:
        appointment = session.query(Appointment).filter_by(id=appointment_id).first()
        if not appointment:
            flash("Appointment not found.", "warning")
            return redirect("/doctor/appointments")

        appointment.status = "Cancelled"
        session.commit()
        flash(f"Appointment #{appointment.appointment_number} has been cancelled.", "danger")
        return redirect("/doctor/appointments")
    except Exception as e:
        print("[ERROR] doctor_mark_cancel:", e)
        flash("Error cancelling appointment.", "danger")
        session.rollback()
        return redirect("/doctor/appointments")
    finally:
        session.close()

@app.route("/doctor/diagnose/<int:appointment_id>", methods=["GET", "POST"])
@login_required
def doctor_diagnose(appointment_id):
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")

    session = SessionLocal()
    try:
        appointment = session.query(Appointment).filter_by(id=appointment_id).first()
        if not appointment:
            flash("Appointment not found.", "danger")
            return redirect("/doctor/appointments")

        # Get patient information
        patient = session.query(Patient).filter_by(id=appointment.patid).first()

        # Fetch existing diagnosis if available
        treatment = session.query(Treatment).filter_by(appointid=appointment.id).first()

        # Get medical history
        medical_history = session.query(MedicalHistory).filter_by(patid=appointment.patid).first()

        if request.method == "POST":
            diagnosis = request.form.get("diagnosis")
            treatment_plan = request.form.get("treatment_plan")
            prescription = request.form.get("prescription")
            notes = request.form.get("notes")
            next_visit_str = request.form.get("next_visit_date")

            next_visit_date = None
            if next_visit_str:
                try:
                    next_visit_date = datetime.strptime(next_visit_str, "%Y-%m-%d").date()
                except ValueError:
                    flash("Invalid date format.", "warning")

            try:
                if treatment:
                    # Update existing record
                    treatment.diagnosis = diagnosis
                    treatment.treatment_plan = treatment_plan
                    treatment.prescription = prescription
                    treatment.notes = notes
                    treatment.next_visit_date = next_visit_date
                else:
                    # Create new record
                    treatment = Treatment(
                        appointid=appointment.id,
                        docid=appointment.docid,
                        patid=appointment.patid,
                        diagnosis=diagnosis,
                        treatment_plan=treatment_plan,
                        prescription=prescription,
                        notes=notes,
                        next_visit_date=next_visit_date,
                    )
                    session.add(treatment)

                # Update or create medical history
                if medical_history:
                    # Append to existing chronic conditions
                    if medical_history.chronic_conditions:
                        medical_history.chronic_conditions += f"\n[{datetime.now().strftime('%Y-%m-%d')}] {diagnosis}"
                    else:
                        medical_history.chronic_conditions = f"[{datetime.now().strftime('%Y-%m-%d')}] {diagnosis}"
                    
                    # Update current medications if prescription exists
                    if prescription:
                        if medical_history.current_medications:
                            medical_history.current_medications += f"\n[{datetime.now().strftime('%Y-%m-%d')}] {prescription}"
                        else:
                            medical_history.current_medications = f"[{datetime.now().strftime('%Y-%m-%d')}] {prescription}"
                else:
                    # Create new medical history
                    medical_history = MedicalHistory(
                        patid=appointment.patid,
                        chronic_conditions=f"[{datetime.now().strftime('%Y-%m-%d')}] {diagnosis}",
                        current_medications=f"[{datetime.now().strftime('%Y-%m-%d')}] {prescription}" if prescription else None,
                    )
                    session.add(medical_history)

                appointment.status = "Completed"
                session.commit()
                flash("Diagnosis saved and medical history updated successfully!", "success")
                return redirect("/doctor/appointment/view/{}".format(appointment.id))

            except Exception as e:
                session.rollback()
                print("[ERROR] doctor_diagnose (POST):", e)
                flash("Error saving treatment details.", "danger")

        return render_template(
            "doctor_diagnose.html",
            appointment=appointment,
            patient=patient,
            treatment=treatment,
            medical_history=medical_history,
        )

    except Exception as e:
        print("[ERROR] doctor_diagnose:", e)
        flash("Error loading diagnosis page.", "danger")
        return redirect("/doctor/appointments")
    finally:
        session.close()


@app.route("/doctor/patients")
@login_required
def doctor_patients():
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")

    session = SessionLocal()
    try:
        doctor = session.query(Doctor).filter_by(uid=current_user.id).first()
        if not doctor:
            flash("Doctor profile not found.", "danger")
            return redirect("/login")

        # Get all unique patients who have appointments with this doctor
        patients_query = (
            session.query(Patient)
            .join(Appointment, Appointment.patid == Patient.id)
            .filter(Appointment.docid == doctor.id)
            .group_by(Patient.id)
            .all()
        )

        patients = []
        for patient in patients_query:
            # Calculate age
            age = calculate_age(patient.dob)
            
            # Get appointment count
            appointment_count = (
                session.query(Appointment)
                .filter(Appointment.patid == patient.id, Appointment.docid == doctor.id)
                .count()
            )
            
            # Get last visit
            last_visit = (
                session.query(Appointment.appoint_date)
                .filter(Appointment.patid == patient.id, Appointment.docid == doctor.id)
                .order_by(Appointment.appoint_date.desc())
                .first()
            )

            patients.append({
                "id": patient.id,
                "name": patient.user.name,
                "gender": patient.gender,
                "age": age,
                "blood_group": patient.blood_group,
                "address": patient.address,
                "appointment_count": appointment_count,
                "last_visit": last_visit,
            })

        return render_template("doctor_patients.html", patients=patients)

    except Exception as e:
        print("[ERROR] doctor_patients:", e)
        flash("Error loading patients.", "danger")
        return redirect("/doctor/dashboard")
    finally:
        session.close()


@app.route("/doctor/availability", methods=["GET", "POST"])
@login_required
def doctor_availability():
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")

    session = SessionLocal()
    try:
        doctor = session.query(Doctor).filter_by(uid=current_user.id).first()
        if not doctor:
            flash("Doctor profile not found.", "danger")
            return redirect("/login")

        if request.method == "POST":
            # Process availability updates for next 7 days
            today = date.today()
            
            for day_index in range(7):
                current_date = today + timedelta(days=day_index)
                available = request.form.get(f"available_{day_index}") == "on"
                start_time_str = request.form.get(f"start_time_{day_index}")
                end_time_str = request.form.get(f"end_time_{day_index}")
                
                # Check if availability record exists
                availability = (
                    session.query(DoctorAvailability)
                    .filter_by(docid=doctor.id, available_date=current_date)
                    .first()
                )
                
                if available and start_time_str and end_time_str:
                    from datetime import datetime
                    start_time = datetime.strptime(start_time_str, "%H:%M").time()
                    end_time = datetime.strptime(end_time_str, "%H:%M").time()
                    
                    if availability:
                        # Update existing
                        availability.available = True
                        availability.start_time = start_time
                        availability.end_time = end_time
                    else:
                        # Create new
                        availability = DoctorAvailability(
                            docid=doctor.id,
                            available_date=current_date,
                            start_time=start_time,
                            end_time=end_time,
                            available=True,
                        )
                        session.add(availability)
                else:
                    # Mark as unavailable
                    if availability:
                        availability.available = False
            
            session.commit()
            flash("Availability updated successfully!", "success")
            return redirect("/doctor/availability")

        # GET request - show availability form
        today = date.today()
        availability_data = {}
        
        for day_index in range(7):
            current_date = today + timedelta(days=day_index)
            day_name = current_date.strftime("%A")
            
            availability = (
                session.query(DoctorAvailability)
                .filter_by(docid=doctor.id, available_date=current_date)
                .first()
            )
            
            availability_data[day_index] = {
                "date": current_date,
                "day_name": day_name,
                "availability": {
                    "available": availability.available if availability else False,
                    "startTime": availability.start_time if availability else None,
                    "endTime": availability.end_time if availability else None,
                    "max_appointments": 10,
                } if availability else None,
            }

        return render_template("doctor_availability.html", availability_data=availability_data)

    except Exception as e:
        print("[ERROR] doctor_availability:", e)
        flash("Error loading availability.", "danger")
        return redirect("/doctor/dashboard")
    finally:
        session.close()


@app.route("/doctor/treatments")
@login_required
def doctor_treatments():
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")

    session = SessionLocal()
    try:
        doctor = session.query(Doctor).filter_by(uid=current_user.id).first()
        if not doctor:
            flash("Doctor profile not found.", "danger")
            return redirect("/login")

        # Get all treatments by this doctor
        treatments_query = (
            session.query(Treatment)
            .join(Appointment, Treatment.appointid == Appointment.id)
            .join(Patient, Treatment.patid == Patient.id)
            .filter(Treatment.docid == doctor.id)
            .order_by(Treatment.treatment_date.desc())
            .all()
        )

        treatments = []
        for treatment in treatments_query:
            treatments.append({
                "id": treatment.id,
                "patient_name": treatment.patient.user.name,
                "diagnosis": treatment.diagnosis,
                "treatment_plan": treatment.treatment_plan,
                "prescription": treatment.prescription,
                "notes": treatment.notes,
                "treatment_date": treatment.treatment_date,
                "appointment_date": treatment.appointment.appoint_date if treatment.appointment else None,
                "next_visit_date": treatment.next_visit_date,
            })

        return render_template("doctor_treatment.html", treatments=treatments)

    except Exception as e:
        print("[ERROR] doctor_treatments:", e)
        flash("Error loading treatments.", "danger")
        return redirect("/doctor/dashboard")
    finally:
        session.close()


@app.route("/doctor/patient/history/<int:patient_id>")
@login_required
def doctor_patient_history(patient_id):
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")

    session = SessionLocal()
    try:
        doctor = session.query(Doctor).filter_by(uid=current_user.id).first()
        if not doctor:
            flash("Doctor profile not found.", "danger")
            return redirect("/login")

        # Get patient information
        patient = session.query(Patient).filter_by(id=patient_id).first()
        if not patient:
            flash("Patient not found.", "danger")
            return redirect("/doctor/patients")

        # Get medical history
        medical_history = session.query(MedicalHistory).filter_by(patid=patient_id).first()

        # Get all treatments for this patient by this doctor
        treatments = (
            session.query(Treatment)
            .join(Appointment, Treatment.appointid == Appointment.id)
            .filter(Treatment.patid == patient_id, Treatment.docid == doctor.id)
            .order_by(Treatment.treatment_date.desc())
            .all()
        )

        # Get all appointments
        appointments = (
            session.query(Appointment)
            .filter(Appointment.patid == patient_id, Appointment.docid == doctor.id)
            .order_by(Appointment.appoint_date.desc())
            .all()
        )

        # Calculate age
        age = calculate_age(patient.dob)

        return render_template(
            "doctor_patient_history.html",
            patient=patient,
            age=age,
            medical_history=medical_history,
            treatments=treatments,
            appointments=appointments,
        )

    except Exception as e:
        print("[ERROR] doctor_patient_history:", e)
        flash("Error loading patient history.", "danger")
        return redirect("/doctor/patients")
    finally:
        session.close()


@app.route("/doctor/profile", methods=["GET"])
@login_required
def doctor_profile():
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")

    session = SessionLocal()
    try:
        doctor = session.query(Doctor).filter_by(uid=current_user.id).first()
        if not doctor:
            flash("Doctor profile not found.", "danger")
            return redirect("/login")

        # Get department
        department = session.query(Department).filter_by(id=doctor.depid).first() if doctor.depid else None

        # Get statistics
        total_appointments = (
            session.query(Appointment)
            .filter(Appointment.docid == doctor.id)
            .count()
        )
        
        completed_appointments = (
            session.query(Appointment)
            .filter(Appointment.docid == doctor.id, Appointment.status == "Completed")
            .count()
        )
        
        total_patients = (
            session.query(Patient)
            .join(Appointment, Appointment.patid == Patient.id)
            .filter(Appointment.docid == doctor.id)
            .group_by(Patient.id)
            .count()
        )

        return render_template(
            "doctor_profile.html",
            doctor=doctor,
            department=department,
            total_appointments=total_appointments,
            completed_appointments=completed_appointments,
            total_patients=total_patients,
        )

    except Exception as e:
        print("[ERROR] doctor_profile:", e)
        flash("Error loading profile.", "danger")
        return redirect("/doctor/dashboard")
    finally:
        session.close()


@app.route("/doctor/profile/update", methods=["POST"])
@login_required
def doctor_profile_update():
    if current_user.role != "doctor":
        flash("Access denied.", "danger")
        return redirect("/login")

    session = SessionLocal()
    try:
        doctor = session.query(Doctor).filter_by(uid=current_user.id).first()
        if not doctor:
            flash("Doctor profile not found.", "danger")
            return redirect("/login")

        # Update profile information
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        specialization = request.form.get("specialization")
        qualification = request.form.get("qualification")
        experience = request.form.get("experience")
        gender = request.form.get("gender")
        
        # Update user information
        user = session.query(User).filter_by(id=current_user.id).first()
        if user and name:
            user.name = name
        
        # Update doctor information
        if specialization:
            doctor.specialization = specialization
        if qualification:
            doctor.qualification = qualification
        if experience:
            doctor.experience = int(experience)
        if gender:
            doctor.gender = gender
        
        session.commit()
        flash("Profile updated successfully!", "success")
        return redirect("/doctor/profile")

    except Exception as e:
        session.rollback()
        print("[ERROR] doctor_profile_update:", e)
        flash("Error updating profile.", "danger")
        return redirect("/doctor/profile")
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
