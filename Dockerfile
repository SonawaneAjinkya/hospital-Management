# Hospital Management Analytics — API + Dashboard image
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the model exists at build time (trains on the bundled sample data)
RUN python3 models/bed_demand_model.py

EXPOSE 8000 8501

# Default: run the API. Override CMD to run the dashboard instead, e.g.
#   docker run -p 8501:8501 hospital-system streamlit run dashboard/app.py --server.address=0.0.0.0
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
