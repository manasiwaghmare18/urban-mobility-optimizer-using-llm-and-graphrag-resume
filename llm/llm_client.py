import os
from openai import OpenAI

# Groq uses OpenAI-compatible format
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

MODEL_NAME = "mixtral-8x7b-32768"


def generate_explanation(route, weather, cost, transport):

    prompt = f"""
You are a senior urban mobility analyst preparing a professional explanation.

Distance: {route['distance_km']} km
Temperature: {weather.get('avg_temperature')}°C
Wind: {weather.get('avg_windspeed')} km/h

Car:
- Cost: ₹{cost['car_cost_rs']}
- Time: {cost['car_time_min']} minutes

Bus:
- Cost: ₹{cost['bus_cost_rs']}
- Time: {cost['bus_time_min']} minutes
- Available: {transport['bus_available']}

Metro:
- Cost: ₹{cost['metro_cost_rs']}
- Time: {cost['metro_time_min']} minutes
- Available: {transport['metro_available']}

Provide clearly:
1. Which option is best by cost.
2. Which option is best by time.
3. Which option is the most balanced overall.
Do not ask questions.
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a professional transport analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Groq Error: {str(e)}"