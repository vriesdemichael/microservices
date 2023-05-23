from dataformats.jsonschema.draft_4 import DRAFT4_SCHEMA
from dataformats.jsonschema.model import Draft4MetaSchema

print(DRAFT4_SCHEMA)

print(Draft4MetaSchema(DRAFT4_SCHEMA).schema())
