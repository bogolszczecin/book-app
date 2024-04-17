# book-app
Address book app based on fastAPI prepared for Solutions30 test.
#recommended code review is trough github codespace which can be opened on project main directory in github and then opening 'Run book app easy way' codespace
![image](https://github.com/bogolszczecin/book-app/assets/133772931/81e012b4-4746-459c-a597-9dc1f1080d28)

#Open terminal in project folder to run commands

# Activate virtual enivrement for app
```bash
source venv/bin/activate
``` 

# Installing dependencies (optional step if you are using code on desktop):
```bash
pip install -r requirements.txt
``` 
sqlalchemy we use to access SQLite
Other libraries are necessary to run fastAPI or manage spatial functionalities of addresses.
# Start and manual of app
Run the app bookApp in terminal opened inside of project folder:
```bash
uvicorn bookApp:app --reload
```
After running the app, open below address on your browser:
[http://127.0.0.1:8000/docs] - if running code on desktop
[https://humble-broccoli-5w9w69rv5v5cpxjg.github.dev/docs] if using github codespace 
originally code from console redirect to port 8000, we need to go to docs directory from that port, by adding docs in the end if using link from console

While you open the address you should see main site of fastAPI swagger as:
![image](https://github.com/bogolszczecin/book-app/assets/133772931/c0645371-2e42-4e2d-83ae-8ad1c1cef079)


Choose desired option from the menu and Press 'try it out' button

![image](https://github.com/bogolszczecin/book-app/assets/133772931/11a4e9be-a3e7-4dec-83ff-f514c12787df)

If tool require filling parameters, fill them along with instructions and press 'Execute' button below. 
You will see results of the query inside of response body below.

To visually preview the address book database, access the following address: (you can also get that information from using 'Read address database function')
[http://127.0.0.1:8000/db]
