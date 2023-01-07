FROM python:3.10

COPY . /knife
RUN pip install /knife

ENV DATABASE_TYPE sqlite
ENV DATABASE_URL /knife-db.sqlite
RUN python /knife/scripts/sqlite_setup.py

CMD exec gunicorn --bind :$PORT knife.__main__:APP
