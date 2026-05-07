FROM python:3.11-slim

WORKDIR /app

# Copy service-specific requirements
COPY flask/products/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY flask/products/app.py /app/

CMD ["python", "app.py"]
