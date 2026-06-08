import models
from database import engine

print("Recreating all tables...")
models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)
print("Tables recreated successfully.")
