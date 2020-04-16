FROM python:3.8.2-buster

WORKDIR /bouncer

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bouncer.py ./
RUN chmod 0755 ./bouncer.py 

CMD ["python", "-u", "./bouncer.py"]
