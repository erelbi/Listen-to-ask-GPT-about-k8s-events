from pymongo import MongoClient
from flask import Flask, request, render_template,jsonify
from atlassian import Confluence
from bson.objectid import ObjectId

app = Flask(__name__)



# MongoDB bağlantısı
client = MongoClient('mongodb://localhost:27017/')
db = client['EVENTK8S']
collection = db['Response']
jira_confluence = Confluence(url="https://confluence.com", token="xxxxxxxxxxxxxxxxxxxxxxxxxx")

@app.route('/')
def index():
    # MongoDB'den verileri çekme
    data_from_mongodb = list(collection.find({}))

    # Verileri HTML şablonuna aktarma
    return render_template('index.html', data=data_from_mongodb)

def generate_list_html(items):
    list_html = "<ul>"
    for item in items:
        list_html += f"<li>{item}</li>"
    list_html += "</ul>"
    return list_html


@app.route('/submit_data', methods=['POST'])
def submit_data():
    id = request.json
    print(id)
    document = collection.find_one({"_id": ObjectId("{}".format(id))})
    if document:
        info_content = """
               <ac:structured-macro ac:name="column">
  <ac:parameter ac:name="width">100px</ac:parameter>
  <ac:rich-text-body>
                    {}
          </ac:rich-text-body>
</ac:structured-macro>  
        """.format(generate_list_html(document['question_gpt']))

        description_content = """
           <ac:structured-macro ac:name="code">
                {}
       </ac:structured-macro>
        """.format(generate_list_html(document['question_web']))

        links_content = """

                <p>{}</p>

        """.format(document['namespace'])
        create_page = jira_confluence.create_page('VSISTEM', document['event'], f"{info_content}{description_content}{links_content}", parent_id=315305050, type='page', representation='storage', editor='v2', full_width=False)
        if create_page['status'] ==  'current':
            return jsonify({"success": "Document create"}), 200
    else:
        return jsonify({"error": "Document not found"}), 404


if __name__ == '__main__':
    app.run(debug=True,host="0.0.0.0",port=8000)
