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
            return dict(current_user=current_user)
    except Exception as e:
        print(f"Context processor error: {e}")

    class SafeUser:
        is_authenticated = False
        name = "Guest"
        role = "guest"

    return dict(current_user=SafeUser())



@app.route("/")
def main():
    return render_template("dashboard.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        session = SessionLocal()
        try:
            user = session.query(User).filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                flash("Logged in successfully.", "success")
                return redirect("/")
            else:
                flash("Invalid username or password.", "danger")
        except Exception as e:
            flash("An error occurred during login.", "danger")
            print(f"Login error: {e}")
        finally:
            session.close()
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect("/login")


# --- Initialization ---
def initialize_app():
    Base.metadata.create_all(engine)
    create_super_admin()
    create_standard_departments()


if __name__ == "__main__":
    initialize_app()
    app.run(debug=True)
