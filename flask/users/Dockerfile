FROM python:3.10

WORKDIR /app

# Copy service-specific requirements
COPY flask/users/requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install -r requirements.txt

# Copy ONLY this microservice’s code
COPY flask/users/app.py /app/

CMD ["python", "app.py"]
