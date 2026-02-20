# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Development server
python app.py

# For production, touch the wsgi file to reload:
# touch ~/apps_wsgi/stg.wsgi
```

## Architecture

This is a Flask REST API using a layered MVC-like architecture with JWT authentication.

### Request Flow

```
app.py → controller/ → rule/ → model/ → MySQL
```

1. **app.py** - Application entry point. Registers routes via `appController.py`, configures JWT (with blacklist), and sets up Swagger UI at `/swagger`
2. **appController.py** - Import hub that re-exports all controllers for registration in app.py
3. **controller/** - Flask MethodView classes handling HTTP requests. Controllers call rules and return responses with status codes
4. **rule/** - Business logic layer. Rules orchestrate model operations and return tuples of (data, status_code)
5. **model/** - Data access layer. Models extend `BaseModel` which provides CRUD operations via query builder

### Key Base Classes

- **BaseModel** (`library/base/BaseModel.py`) - ORM-like base with `find()`, `find_one()`, `save()`, `update()`, `delete()`. Supports chained methods: `.where()`, `.order()`, `.limit()`, `.offset()`, `.field()`
- **QueryBuilder** (`library/base/QueryBuilder.py`) - SQL builder inherited by BaseModel. Abstract methods: `table()`, `fields()`, `pk()`

### Creating a New Endpoint

1. Create model in `model/` extending `BaseModel`, implementing `table()`, `pk()`, `fields()`
2. Create rule in `rule/` with business logic methods
3. Create controller in `controller/` extending `MethodView`
4. Export controller in `appController.py`
5. Register route in `app.py` with `api.add_resource()`

### Model Definition Pattern

```python
class ExampleModel(BaseModel):
    def table(self):
        return 'table_name'

    def pk(self):
        return 'id'

    def fields(self):
        return {"db_column": "alias", ...}
```

### Configuration

- **kernel/dump.py** - Contains all configuration (JWT settings, MySQL credentials, utilities). Imported as `memory`
- **schema/** - JSON Schema files for request validation, used via `Funcao.schema('path/to/schema.json')`

### Utilities

- **library/Funcao.py** - Static helper methods for date formatting, random generation, JSON schema validation
- **library/MySql.py** - MySQL connection wrapper using pymysql
- **model/ControllerError.py** or **library/ControllerError.py** - Standardized error handling and logging
