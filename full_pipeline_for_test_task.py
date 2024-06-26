# -*- coding: utf-8 -*-
"""full_pipeline_for_test_task.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1wVvefJ1xuogffstE158fiwDwxfhwTChF
"""

# Commented out IPython magic to ensure Python compatibility.
# %pip install --upgrade openai --quiet PyMuPDF streamlit

from openai import OpenAI
import base64
import json
import fitz
import streamlit as st
import zipfile
import pandas as pd


SAVE_PATH = "pdf_features.png"


MODEL = "gpt-4o"


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def extract_data_from_pdf(client, base64_image):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that return json. Help me with reading this image!"},
            {"role": "user", "content": [
                {"type": "text", "text": "Your task is next. You receive the image with agenda. Read the title and summary of each lecture"\
                                         "and provide me json with it."},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{base64_image}"}
                 }
            ]}
        ],
        temperature=0.0,
    )
    json_answer = response.choices[0].message.content
    json_answer = json_answer.replace('json\n', '')
    json_answer = ''.join([str_el.strip() for str_el in json_answer.split('\n')])
    json_answer = json_answer.replace("```", '')
    json_answer = json.loads(json_answer)
    return '\n'.join([f"{dictionary['title']}: {dictionary['summary']}"
                      for dictionary in json_answer['lectures']])


def send_data_to_openai(client, json_data, lectures_title_and_summary_combined):
    MODEL = 'gpt-4-turbo'
    content = """
                You are helpful assistan which should determine the hypothetical customer.
                You get the two type of features and based on them should analyse if person could be our client.
                After analysis you respond and if person is a customer, explain your choice in comprehesive manner.
            """
    input_query = f"""
                  We try to sell a two-day training course on "Regulation, Quality, and Compliance in ADC Manufacturing,".
                  And you receive the title and the summary of the lectures: {lectures_title_and_summary_combined}.
                  You get the JSON file with fields which represent information about user, use as much data as you need.
                  You can read it from here: {json_data}.
                  Based on the provided data, you should determine if the user could be our customer.
                  If your answer is positive, respond 'Yes' and explain it, also provide the list of lessons in which customer could be interested.
                  If your answer is negative, respond using only one word 'No'.
                  Respond in the next manner: "Yes. And the reasons for this..." or "No".
              """
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": content},
                  {"role": "user", "content": input_query}])
    feedback = completion.choices[0].message.content
    content = """
             You are helpful assistant which gets as input information about person in json format and feedback if person could be our customer or not.
             If a person is our customer, use the information from json to construct for this person proposition to attend our course.
             If the person could be our customer based on the answer of previous AI agent, ignore the stage with generating message to the customer.
          """
    input_query = f"""
                      We try to sell a two-day training course on "Regulation, Quality, and Compliance in ADC Manufacturing,".
                      You receive the data about the current user {json_data} and feedback from previous AI agent {feedback}
              """
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": content},
            {"role": "user", "content": input_query}]
        )
    messages = completion.choices[0].message.content

    return feedback, messages


def extract_pdf_and_save(pdf_data, save_path):
    pdf_document = fitz.open(stream=pdf_data.read(), filetype="pdf")
    page = pdf_document[5]
    pix = page.get_pixmap()
    pix.save(save_path)


def extract_json_from_zip(zip_file):
    json_files = []
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        for file in zip_ref.namelist():
            if file.endswith('.json'):
                with zip_ref.open(file) as json_file:
                    json_files.append(json.load(json_file))
    return json_files


st.title("AI agent for defining the hypothetical customer")
pdf_file = st.file_uploader("Upload a PDF file", type=["pdf"])
zip_file = st.file_uploader("Upload a ZIP file containing JSON files", type=["zip"])
with st.form('ticket_form'):
    openai_api_key = st.text_input("Input the OPEN AI API key")
    submit_button = st.form_submit_button("Send key to the server")

client = OpenAI(api_key=openai_api_key)

if pdf_file is not None and zip_file is not None and submit_button:
    extract_pdf_and_save(pdf_file, SAVE_PATH)
    json_files = extract_json_from_zip(zip_file)
    if json_files:
        st.write(f"Found {len(json_files)} JSON files. Sending to OpenAI endpoint...")
        base64_image = encode_image(SAVE_PATH)
        lectures_title_and_summary_combined = extract_data_from_pdf(client,
                                                                    base64_image)

        results = pd.DataFrame([], columns=['json_name', 'feedback', 'message_to_the_client'])
        for json_data in json_files:
            feedback, message = send_data_to_openai(client,
                                                    json_data,
                                                    lectures_title_and_summary_combined)
            results = pd.concat([results,
                                 pd.DataFrame({'json_name': json_data,
                                               'feedback': feedback,
                                               'message_to_the_client': message})])

        st.download_button(
            "Press to Download",
            results,
            "file.csv",
            "text/csv",
            key='download-csv'
        )
elif zip_file is None and submit_button:
    st.write("No JSON files found in the ZIP file.")
