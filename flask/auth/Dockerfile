FROM python:3.11-slim

WORKDIR /app

# Copy service-specific requirements
COPY flask/auth/requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy ONLY this microservice's code
COPY flask/auth/app.py /app/

CMD ["python", "app.py"]
