**Tôi vừa làm theo cách bạn hướng dẫn kết quả trả về như vậy**  
PS F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\> cd backend  
\>\> .venv\\Scripts\\activate  
(.venv) PS F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\> (Set-ExecutionPolicy \-Scope Process \-ExecutionPolicy RemoteSigned) ; (& "f:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\\.venv\\Scripts\\Activate.ps1")  
(.venv) PS F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\> python manage.py shell \-c "from django.db import connection; d=connection.settings\_dict; print('ENGINE:', d\['ENGINE'\]); print('HOST:', d.get('HOST'))"  
26 objects imported automatically (use \-v 2 for details).

ENGINE: django.db.backends.postgresql  
HOST: aws-0-ap-northeast-1.pooler.supabase.com  
(.venv) PS F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\> python manage.py shell \-c "from django.contrib.auth import authenticate; print('AUTH:', authenticate(username='admin', password='admin12345'))"  
26 objects imported automatically (use \-v 2 for details).

AUTH: admin (1)  
(.venv) PS F:\\OneDrive\\20221508\_Material\_AMG\\20260605\_Dev\_System\_Training\\He thong dao tao\\Training\_SaaS\_Python\\backend\>   
Bạn kiểm tra xem vấn đề đang nằm ở đâu nhé. Tôi đã làm đúng theo bạn hướng dẫn chưa?