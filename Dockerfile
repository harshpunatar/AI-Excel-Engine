#Python image
FROM python:3.9-slim

#working directory
WORKDIR /app

COPY requirements.txt .

#Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

#Copy the rest of your application code
COPY . .

#FastAPI Port
EXPOSE 8000

#Start the app
CMD ["uvicorn", "main4:app", "--host", "0.0.0.0", "--port", "8000"]