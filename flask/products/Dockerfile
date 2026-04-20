FROM python:3.10

WORKDIR /app

# Copy service-specific requirements
COPY flask/products/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY flask/products/app.py /app/

CMD ["python", "app.py"]
