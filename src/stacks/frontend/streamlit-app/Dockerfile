FROM --platform=linux/arm64 arm64v8/python:latest
EXPOSE 8501
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN  pip3 install --upgrade pip --no-cache-dir && pip3 install -r requirements.txt --no-cache-dir
COPY . .
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
# Command overriden by docker-compose
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
#CMD streamlit run app.py