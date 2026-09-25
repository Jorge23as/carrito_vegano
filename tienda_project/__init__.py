# PyMySQL se instaló en vez de mysqlclient porque este equipo no tiene los
# headers de compilación de MariaDB/MySQL (libmariadb-dev). Esta línea hace
# que Django (y cualquier código que importe MySQLdb) use PyMySQL por debajo,
# sin cambiar nada más del ORM.
import pymysql

pymysql.install_as_MySQLdb()

# Django >= 4.1 valida que la versión reportada por el driver sea >= 2.2.1,
# pensando en mysqlclient. PyMySQL reporta su propia versión (1.1.1), que es
# "menor" numéricamente aunque el driver funciona perfecto, así que hay que
# decirle a Django que finja una versión válida. Workaround documentado y
# usado ampliamente por el propio proyecto PyMySQL para este caso.
pymysql.version_info = (2, 2, 4, "final", 0)
