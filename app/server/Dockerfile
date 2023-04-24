# Use an official Python image as the base image
FROM python:3.9

# Set the working directory
WORKDIR /usr/app



COPY requirements.txt requirements.txt

# Install the dependencies
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt --use-feature=fast-deps
RUN apt-get update
RUN apt-get install -y curl

# Copy the entire workspace
COPY app/. .

ENV PYTHONPATH="/usr/"

# Expose the port the app runs on
EXPOSE 8000

# Start the application
CMD ["python", "server/main.py"]





