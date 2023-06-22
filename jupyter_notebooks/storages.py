import sqlite3
from pathlib import Path

class BaseField():
    """
    Base class for fields intended to be used with SQL databases
    """

    priority = 0

    def __init__(self, use_to_identify: bool=False, *args, **kwargs) -> None:

        if self.priority == None:
            raise NotImplementedError("`priority` attribute must be specified when creating new field class")
        elif not isinstance(self.priority, int):
            raise TypeError(f"`priority` attribute must be an int, not '{self.priority}'")


        if isinstance(use_to_identify, bool):
            self.use_to_identify = use_to_identify
        else:
            raise TypeError(f"`use_to_identify` argument must be a bool, not '{use_to_identify}'")


        self.str_representation = None

    def can_use_for_identification(self) -> bool:
        return self.use_to_identify

    def create_str_representation(self) -> str:
        """
        Create and return a string representation of the field
        """

        raise NotImplementedError()

    def get_field_as_string(self) -> str:
        """
        Returns str representation of the field so that it can be directly injected into SQL queries
        for example when creating tables

        Gives something like "name INTEGER NOT_NULL"
        """

        self.str_representation = self.create_str_representation()
        return self.str_representation

    def set_priority(self, priority: int=None):
        self.priority = int(priority)

    def get_priority(self) -> int:
        return self.priority

    
class SQLiteField(BaseField):
    data_type = None

    def __init__(self, name: str=None, null: bool=False, primary_key: bool=False, attrs: list=[], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if self.data_type == None:
            raise NotImplementedError("`data_type` attribute must be specified when creating new field class")
        elif not isinstance(self.data_type, str):
            raise TypeError(f"`data_type` attribute must be a string, not '{self.data_type}'")


        if isinstance(name, str):
            self.name = name
        else:
            raise TypeError(f"`name` argument must be a str, not '{name}'")


        if isinstance(null, bool):
            self.null = null
        else:
            raise TypeError(f"`null` argument must be a bool, not '{null}'")


        if isinstance(primary_key, bool):
            self.primary_key = primary_key
            if primary_key:
                self.priority += 1
        else:
            raise TypeError(f"`primary_key` argument must be a bool, not '{null}'")

        if len(attrs) == 0:
            self.attrs = attrs

        elif isinstance(attrs, list) and len(attrs) != 0:
            is_list_of_strings = all([isinstance(attr, str) for attr in attrs])
            if is_list_of_strings:
                self.attrs = attrs
                
        else:
            raise TypeError("`attrs` argument must be a list of string")


    def create_str_representation(self) -> str:

        rv = f"{self.name} {self.data_type}"

        if not self.null and not self.primary_key:
            rv += " NOT NULL "

        if self.primary_key:
            rv += " PRIMARY KEY AUTOINCREMENT "

        for attribute in self.attrs:
            rv += f" {attribute}"

        return rv


class IntegerFieldSQLite(SQLiteField):
    data_type = "INTEGER"

class TextFieldSQLite(SQLiteField):
    data_type = "TEXT"

class BoolFieldSQLite(SQLiteField):
    data_type = "BOOL"

class ConstraintField(BaseField):
    priority = -1

    def __init__(self, constraint: str=None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if isinstance(constraint, str):
            self.constraint = constraint
        else:
            raise TypeError(f"`constrain` argument must be a str, not '{constraint}'")

    def create_str_representation(self) -> str:
        return self.constraint

    
class BaseTable:
    def __init__(self, name: str=None, fields: list=None) -> None:
        
        if isinstance(name, str):
            self.name = name
        else:
            raise TypeError(f"`name` argument must be a str, not '{name}'")


        if isinstance(fields, list):
    
            is_list_of_fields = all([isinstance(field, BaseField) for field in fields])
            if is_list_of_fields:
                self.fields = fields

        elif len(fields) == 0:
            self.fields = fields
        else:
            raise TypeError("`fields` argument must be a list of fields")

    def add_field(self, field):
        if isinstance(field, BaseField):
            self.fields.append(field)
        else:
            raise TypeError("`field` argument must be a field object")

    def get_ordered_fields(self) -> list:
        ordered_fields = sorted(self.fields, key=lambda x: x.get_priority(), reverse=True)

        return ordered_fields

    def get_fields(self) -> list:
        return self.get_ordered_fields()

    def get_identification_fields(self) -> list:
        rv = [field for field in self.get_fields() if field.can_use_for_identification()]
        return rv

    def get_primary_key_field(self) -> SQLiteField:
        rv = [field for field in self.get_fields() if field.primary_key]
        return rv[0]

    def get_fields_by_priority(self, priority: int=None) -> list:
        if isinstance(priority, int):
            self.priority = priority
        else:
            raise TypeError(f"`priority` argument must be an int, not '{priority}'")

        rv = [field for field in self.get_fields() if field.get_priority() == priority]
        return rv

class SimpleTable(BaseTable):
    pass
    

class BaseStorage():
    fields = None
    row_factory = sqlite3.Row
    DB_NAME = "robot_schedule2.db"

    def __init__(self, parent_dir: str) -> None:
        self.database_path = Path(parent_dir, self.DB_NAME)
        self.base_fields = None
        self.custom_fields = None


        self.tables = {
            "schedules":
                BaseTable(name="schedules", fields=[
                    IntegerFieldSQLite(name="id", primary_key=True),
                    BoolFieldSQLite(name="is_completed", null=False, default=0),
                    BoolFieldSQLite(name="in_progress", null=False, default=0),
                    BoolFieldSQLite(name="timestamp", null=False),
                    IntegerFieldSQLite(name="x", null=False),
                    IntegerFieldSQLite(name="y", null=False),
                    IntegerFieldSQLite(name="z", null=False),
                ]),
        }


        self.conn = None


    def connect(self) -> sqlite3.Connection:
        try:
            self.conn = sqlite3.connect(str(self.database_path))
            self.conn.row_factory = self.row_factory
        except sqlite3.Error as e:
            raise e

        return self.conn

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args, **kwargs):
        self.conn.close()
    
    def delete_table(self, table:BaseTable, perform: bool=False):
        c = self.conn.cursor()
        
        if perform:
            c.execute(f"DROP TABLE IF EXISTS {table.name}")

    def delete_db(self, perform: bool=False):
        for key, table in self.tables.items():
            self.delete_table(table, perform)
    
    def get_all_rows(self) -> list:
        rv = []

        for key, table in self.tables.items():
            rv.append(self.get_all_rows_in_table(table))

        return rv

    def get_all_rows_in_table(self, table: BaseTable) -> list:
        c = self.conn.cursor()
 
        c.execute(f"SELECT * FROM {table.name}")

        return c.fetchall()


    def insert_row(self, row: dict, table_name: str) -> None:
        c = self.conn.cursor()

        # dynamically construct a query based on row size which later can be parametrized
        field = ', '.join([k for k in row.keys()])
        questions_marks = ', '.join(['?' for i in row.values()])
        sql = f"INSERT INTO {table_name}({field}) VALUES ({questions_marks});"

        c.execute(sql, (*row.values(),))

        self.conn.commit()
        
  
    def create_tables_if_not_exist(self) -> None:
        c = self.conn.cursor()

        for key, table in self.tables.items():

            # create a string of all field that can be directly appended to sql query
            field_strings = []
            for field in table.get_fields():
                field_str = field.get_field_as_string()
                field_strings.append(field_str)

            fields = ', '.join(field_strings)
            sql = f"CREATE TABLE IF NOT EXISTS {table.name} ({fields});"

            c.execute(sql)
        
        self.conn.commit()
