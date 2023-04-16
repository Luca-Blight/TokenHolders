FROM python:3.9-alpine

WORKDIR /app/indexers

COPY requirements.txt ./
RUN pip3 install -r requirements.txt 

COPY app/ ./app

CMD ["python", "app/indexers/main.py"]

