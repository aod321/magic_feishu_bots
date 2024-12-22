FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source code
COPY latest_paper_bot.py .

# Create logs directory
RUN mkdir -p logs

# Run the bot
CMD ["python", "latest_paper_bot.py"] 