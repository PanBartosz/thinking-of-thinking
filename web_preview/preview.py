import re
from markupsafe import Markup, escape
from jinja2 import pass_eval_context, Environment, PackageLoader, select_autoescape
from flask import Flask, render_template, request
from parseQDPX import *

@pass_eval_context
def nl2br(eval_ctx, value):
    br = "<br>\n"

    if eval_ctx.autoescape:
        value = escape(value)
        br = Markup(br)

    result = "\n\n".join(
        f"<p>{br.join(p.splitlines())}</p>"
        for p in re.split(r"(?:\r\n|\r(?!\n)|\n){2,}", value)
    )
    return Markup(result) if eval_ctx.autoescape else result


env = Environment(loader=PackageLoader("preview"), autoescape=select_autoescape(['html', 'htm', 'xml']))
env.filters['nl2br'] = nl2br
upload_template = env.get_template("upload.html")
preview_template = env.get_template("preview.html")

app = Flask(__name__)

@app.route('/upload')
def upload_file():
   return upload_template.render()

@app.route('/preview', methods = ['GET', 'POST'])
def preview():
	if request.method == 'POST':
		f = request.files['file']
		project = read_qdpx_file(f)
		return preview_template.render(project = project, filename = f.filename)

if __name__ == '__main__':
   app.run(debug = True)