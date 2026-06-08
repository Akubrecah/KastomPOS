import models
from database import Base

print("--- MODEL FIELDS ---")
for mapper in Base.registry.mappers:
    cls = mapper.class_
    name = cls.__name__
    columns = [col.key for col in mapper.columns]
    print(f"{name}: {columns}")
