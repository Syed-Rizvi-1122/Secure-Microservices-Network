FROM python:3.10

WORKDIR /app

# Copy service-specific requirements
COPY flask/orders/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY flask/orders/app.py /app/

CMD ["python", "app.py"]
