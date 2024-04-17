import sqlite3
import json
import string
from openai import OpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt
from termcolor import colored  

GPT_MODEL = "gpt-4"
client = OpenAI()

@retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
def chat_completion_request(messages, tools=None, tool_choice=None, model=GPT_MODEL):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
        return response
    except Exception as e:
        # print("Unable to generate ChatCompletion response")
        # print(f"Exception: {e}")
        return e


def describe_vehicle(vehicle):
    # Unpack the tuple into variables for better readability
    (_, vin, stock_number, is_new, year, make, model, body_style, trim, odometer, color, _, price, image_url, url, interior_color, fuel_type) = vehicle
    is_new = "new" if is_new == 1 else "used"
    body_style = body_style if body_style is not None else "not specified"
    interior_color = interior_color if interior_color is not None else "not specified"
    fuel_type = fuel_type if fuel_type is not None else "not specified"
    description = (
        f"This {is_new} {year} {make} {model} ({body_style}) "
        f"with {trim.strip()} trim, is available in {color} exterior and {interior_color} interior. "
        f"It has {odometer} miles on the odometer. "
        f"The vehicle, with VIN {vin} and stock number {stock_number}, is priced at ${price:.2f}. "
        f"See more at {url}"
    )
    return description


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_vehicle_details",
            "description": "Use this finction to get vehicle details. There should be atleast one argument. We may not require all the arguments. Do not mention the usage of this function in responsesAre. Do not mention any not specified values in the response.",
            "parameters": {
                "type": "object",
                "properties": {
                    "color": {
                        "type": "string",
                        "description": "The color of the vehicle, e.g. red, orange",
                    },
                    "vin": {
                        "type": "string",
                        "description": "The vin of the vehicle, e.g. 3GNCJLSB1GL133008",
                    },
                    "year":{
                        "year": "string",
                        "description": "The manufactured year of the vehicle, e.g. <=2014 or =>2022 or =2023",
                    },
                    "isNew":{
                        "isNew": "boolean",
                        "description": "Weather the vehicle is new or not, e.g. 0 or 1",
                    },
                    "make":{
                        "make": "string",
                        "description": "The make of the vehicle, e.g. Chevrolet or Nissan",
                    },
                    "model":{
                        "model": "string",
                        "description": "The model of the vehicle, e.g. Camry or Sonata",
                    },
                    "trim":{
                        "model": "string",
                        "description": "The trim of the vehicle, e.g. Sedan 4D XLE or Utility 4D C",
                    },
                    "odometer":{
                        "odometer": "string",
                        "description": "The mileage on the vehicle, e.g. <=68748 or >=176604",
                    },
                },
                "required": ["color", "vin","year", "isNew", "make", "model", "trim", "odometer"],
            },
        }
    }
]

def get_user_input(prompt):
    """Function to get input from the user."""
    return input(prompt)

def safe_sql_string(value):
    if value is not None:
        escaped_value = value.replace("'", "''")
        return f"%{escaped_value}%"
    return None


def create_select_query(color=None, year=None, vin=None, isNew=None, make=None, model=None, trim=None, odometer=None):
    base_query = "SELECT * FROM vehicles"
    conditions = []

    if color is not None:
        color = safe_sql_string(color)
        conditions.append(f"color like '{color}'")
    if year is not None:
        conditions.append(f"year  {year}")
    if vin is not None:
        vin = safe_sql_string(vin)
        conditions.append(f"vin like '{vin}'")
    if isNew is not None:
        conditions.append(f"is_new = {isNew}")
    if make is not None:
        make = safe_sql_string(make)
        conditions.append(f"make LIKE '{make}'")
    if model is not None:
        model = safe_sql_string(model)
        conditions.append(f"model LIKE '{model}'")
    if trim is not None:
        trim = safe_sql_string(trim)
        conditions.append(f"trim LIKE '{trim}'")
    if odometer is not None:
        conditions.append(f"odometer {odometer}")

    if conditions:
        query = f"{base_query} WHERE {' AND '.join(conditions)}"
    else:
        query = base_query
    query += " LIMIT 10"
    return query

def get_vehicle_details(color=None, year=None, vin=None, isNew=None, make=None, model=None, trim=None, odometer=None):
    conn = sqlite3.connect('Inventory.db')
    cursor = conn.cursor();
    # print("color =", color, "year =", year, "vin=", vin, "isNew=", isNew)
    query = create_select_query(color, year, vin, isNew, make, model, trim, odometer)
    print("query-------------------", query)
    cursor.execute(query)
    rows = cursor.fetchall()
    # print("rows---------",rows )
    vehicle_descriptions = [describe_vehicle(vehicle) for vehicle in rows]
    full_description = "\n\n".join(vehicle_descriptions)
    # print("full_description-----", full_description)
    return full_description

messages = []

messages.append({"role": "system", "content": "You are to provide information about vehicles from db. All the parameters are not required. Make sure there is atleast one parameter. Don't make assumptions about what values to plug into functions. Ask for clarification if a user request is ambiguous. If user asks for a picture, provide them with image_url from database"})
while True:
    user_query = get_user_input("")
    if user_query.lower() == 'exit':
        break
    messages.append({"role": "user", "content": user_query.lower()})

    chat_response = chat_completion_request(
        messages, tools=tools
    )
    response_message = chat_response.choices[0].message
    print("\n\n", response_message.content);
    tool_calls = response_message.tool_calls
    if(tool_calls):
        available_functions = {
            "get_vehicle_details": get_vehicle_details, 
        } 
        messages.append(response_message)
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)
            function_response = function_to_call(
                color=function_args.get("color"),
                vin=function_args.get("vin"),
                year=function_args.get("year"),
                isNew= function_args.get("isNew"),
                make=  function_args.get("make"),
                model=  function_args.get("model"),
                trim=  function_args.get("trim"),
                odometer=  function_args.get("odometer"),
                

            )
            if len(function_response) == 0:
                function_response = "No vehicles available"
            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                }
            ) 
        # print("messages-------------", messages)
        second_response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
        ) 
        messages.append(second_response.choices[0].message) 
        print("\n\n", second_response.choices[0].message.content);   




    

