Traceback (most recent call last):  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\base\\base.py", line 279, in ensure\_connection  
    self.connect()  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\utils\\asyncio.py", line 26, in inner  
    return func(\*args, \*\*kwargs)  
           ^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\base\\base.py", line 256, in connect  
    self.connection \= self.get\_new\_connection(conn\_params)  
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\utils\\asyncio.py", line 26, in inner  
    return func(\*args, \*\*kwargs)  
           ^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\postgresql\\base.py", line 333, in get\_new\_connection  
    connection \= self.Database.connect(\*\*conn\_params)  
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\psycopg2\\\_\_init\_\_.py", line 135, in connect  
    conn \= \_connect(dsn, connection\_factory=connection\_factory, \*\*kwasync)  
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
psycopg2.OperationalError: connection to server at "aws-0-ap-northeast-1.pooler.supabase.com" (54.64.190.72), port 5432 failed: FATAL:  password authentication failed for user "postgres"  
connection to server at "aws-0-ap-northeast-1.pooler.supabase.com" (54.64.190.72), port 5432 failed: FATAL:  password authentication failed for user "postgres"

The above exception was the direct cause of the following exception:

Traceback (most recent call last):  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\manage.py", line 22, in \<module\>  
    main()  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\manage.py", line 18, in main  
    execute\_from\_command\_line(sys.argv)  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\core\\management\\\_\_init\_\_.py", line 443, in execute\_from\_command\_line  
    utility.execute()  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\core\\management\\\_\_init\_\_.py", line 437, in execute  
    self.fetch\_command(subcommand).run\_from\_argv(self.argv)  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\core\\management\\base.py", line 420, in run\_from\_argv  
    self.execute(\*args, \*\*cmd\_options)  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\core\\management\\base.py", line 464, in execute  
    output \= self.handle(\*args, \*\*options)  
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\core\\management\\base.py", line 111, in wrapper  
    res \= handle\_func(\*args, \*\*kwargs)  
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\core\\management\\commands\\migrate.py", line 114, in handle  
    executor \= MigrationExecutor(connection, self.migration\_progress\_callback)  
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\migrations\\executor.py", line 18, in \_\_init\_\_  
    self.loader \= MigrationLoader(self.connection)  
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\migrations\\loader.py", line 59, in \_\_init\_\_  
    self.build\_graph()  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\migrations\\loader.py", line 288, in build\_graph  
    self.applied\_migrations \= recorder.applied\_migrations()  
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\migrations\\recorder.py", line 89, in applied\_migrations  
    if self.has\_table():  
       ^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\migrations\\recorder.py", line 63, in has\_table  
    with self.connection.cursor() as cursor:  
         ^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\utils\\asyncio.py", line 26, in inner  
    return func(\*args, \*\*kwargs)  
           ^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\base\\base.py", line 320, in cursor  
    return self.\_cursor()  
           ^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\base\\base.py", line 296, in \_cursor  
    self.ensure\_connection()  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\utils\\asyncio.py", line 26, in inner  
    return func(\*args, \*\*kwargs)  
           ^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\base\\base.py", line 278, in ensure\_connection  
    with self.wrap\_database\_errors:  
         ^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\utils.py", line 94, in \_\_exit\_\_  
    raise dj\_exc\_value.with\_traceback(traceback) from exc\_value  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\base\\base.py", line 279, in ensure\_connection  
    self.connect()  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\utils\\asyncio.py", line 26, in inner  
    return func(\*args, \*\*kwargs)  
           ^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\base\\base.py", line 256, in connect  
    self.connection \= self.get\_new\_connection(conn\_params)  
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\utils\\asyncio.py", line 26, in inner  
    return func(\*args, \*\*kwargs)  
           ^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\postgresql\\base.py", line 333, in get\_new\_connection  
    connection \= self.Database.connect(\*\*conn\_params)  
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\psycopg2\\\_\_init\_\_.py", line 135, in connect  
    conn \= \_connect(dsn, connection\_factory=connection\_factory, \*\*kwasync)  
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
django.db.utils.OperationalError: connection to server at "aws-0-ap-northeast-1.pooler.supabase.com" (54.64.190.72), port 5432 failed: FATAL:  password authentication failed for user "postgres"  
connection to server at "aws-0-ap-northeast-1.pooler.supabase.com" (54.64.190.72), port 5432 failed: FATAL:  password authentication failed for user "postgres"

Traceback (most recent call last):  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\utils.py", line 105, in \_execute  
    return self.cursor.execute(sql, params)  
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
psycopg2.errors.UndefinedTable: relation "accounts\_tenant" does not exist  
LINE 1: ...nt"."status", "accounts\_tenant"."created\_at" FROM "accounts\_...  
                                                             ^

The above exception was the direct cause of the following exception:

Traceback (most recent call last):  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\manage.py", line 22, in \<module\>  
    main()  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\manage.py", line 18, in main  
    execute\_from\_command\_line(sys.argv)  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\core\\management\\\_\_init\_\_.py", line 443, in execute\_from\_command\_line  
    utility.execute()  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\core\\management\\\_\_init\_\_.py", line 437, in execute  
    self.fetch\_command(subcommand).run\_from\_argv(self.argv)  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\core\\management\\base.py", line 420, in run\_from\_argv  
    self.execute(\*args, \*\*cmd\_options)  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\core\\management\\base.py", line 464, in execute  
    output \= self.handle(\*args, \*\*options)  
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\accounts\\management\\commands\\seed\_admin.py", line 15, in handle  
    tenant, \_ \= Tenant.objects.get\_or\_create(name=options\['tenant'\])  
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\models\\manager.py", line 87, in manager\_method  
    return getattr(self.get\_queryset(), name)(\*args, \*\*kwargs)  
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\models\\query.py", line 987, in get\_or\_create  
    return self.get(\*\*kwargs), False  
           ^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\models\\query.py", line 635, in get  
    num \= len(clone)  
          ^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\models\\query.py", line 372, in \_\_len\_\_  
    self.\_fetch\_all()  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\models\\query.py", line 2000, in \_fetch\_all  
    self.\_result\_cache \= list(self.\_iterable\_class(self))  
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\models\\query.py", line 95, in \_\_iter\_\_  
    results \= compiler.execute\_sql(  
              ^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\models\\sql\\compiler.py", line 1624, in execute\_sql  
    cursor.execute(sql, params)  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\utils.py", line 122, in execute  
    return super().execute(sql, params)  
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\utils.py", line 79, in execute  
    return self.\_execute\_with\_wrappers(  
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\utils.py", line 92, in \_execute\_with\_wrappers  
    return executor(sql, params, many, context)  
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\utils.py", line 100, in \_execute  
    with self.db.wrap\_database\_errors:  
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\utils.py", line 94, in \_\_exit\_\_  
    raise dj\_exc\_value.with\_traceback(traceback) from exc\_value  
  File "F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Lib\\site-packages\\django\\db\\backends\\utils.py", line 105, in \_execute  
    return self.cursor.execute(sql, params)  
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  
django.db.utils.ProgrammingError: relation "accounts\_tenant" does not exist  
LINE 1: ...nt"."status", "accounts\_tenant"."created\_at" FROM "accounts\_...  
                                                             ^  
