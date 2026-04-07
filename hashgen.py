from werkzeug.security import generate_password_hash #always use hashed passwords for security in DB

print(generate_password_hash("Admin1"))
print(generate_password_hash("Resident1"))
print(generate_password_hash("Staff1"))