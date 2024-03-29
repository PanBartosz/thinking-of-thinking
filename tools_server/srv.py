import re
from markupsafe import Markup, escape
from jinja2 import pass_eval_context, Environment, PackageLoader, select_autoescape
from flask import Flask, render_template, request, url_for, send_from_directory
from parseQDPX import read_qdpx_file, Project
from extract_fragments_files import extract_fragments, make_qdpx_project
import shutil
from compare_pair import ProjectPair


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


# Prepare the environment
env = Environment(loader=PackageLoader("srv"),
                  autoescape=select_autoescape(['html', 'htm', 'xml'])
                  )

env.filters['nl2br'] = nl2br

# Read templates
upload_template = env.get_template("upload.html")
preview_template = env.get_template("preview.html")
extract_template = env.get_template("extract.html")
compare_template = env.get_template("compare.html")
upload_two_template = env.get_template("upload_two.html")

app = Flask(__name__)


# QDPX files viewer
@app.route('/upload')
def upload_file():
    return upload_template.render()


@app.route('/preview', methods=['GET', 'POST'])
def preview():
    if request.method == 'POST':
        f = request.files['file']
        lu_code_name = request.form['lu-code-name']
        f_code_name = request.form['f-code-name']
        #g_code_name = request.form['g-code-name']
        g_code_name = "Grammar"
        project, sources = read_qdpx_file(f)
        project = Project(project, sources, lu_code_name,
                          f_code_name, g_code_name)
        return preview_template.render(project=project, filename=f.filename)
    else:
        return "Something went wrong..."

# QDPX files comparator
@app.route('/upload_two')
def upload_tw_file():
    return upload_two_template.render()

@app.route('/compare', methods=['GET', 'POST'])
def compare():
    if request.method == 'POST':
        f_first = request.files['file_first']
        f_second = request.files['file_second']
        lu_code_name = request.form['lu-code-name']
        f_code_name = request.form['f-code-name']
        g_code_name = "Grammar"
        project_first, sources_first = read_qdpx_file(f_first)
        project_second, sources_second = read_qdpx_file(f_second)
        project_first = Project(project_first, sources_first, lu_code_name,
                          f_code_name, g_code_name)
        project_second = Project(project_second, sources_second, lu_code_name,
                          f_code_name, g_code_name)
                        
        project_pair = ProjectPair(project_first, project_second)

        return compare_template.render(project_pair=project_pair,
                                        filename_first=f_first.filename,
                                        filename_second=f_second.filename
                                        )
    else:
        return "Something went wrong..."

# Fragments extractor
@app.route('/extract', methods = ['GET', 'POST'])
def extract_file():
    if request.method == 'POST':
        f = request.files['file']
        fname = "fragments_" + f.filename
        unit_code = request.form["fragment-code-name"]
        user = request.form["user-name"]
        project, sources = read_qdpx_file(f)
        documents, links, files, = extract_fragments(
            project, sources, unit_code, f)
        qdpx_archive = make_qdpx_project(documents, links, files, fname, project, user)
        shutil.copyfile(fname, f'data/{fname}')
        return extract_template.render(fname=fname)
    else:
        return extract_template.render()

@app.route('/data/<path:filepath>')
def data(filepath):
    return send_from_directory('data', filepath)

if __name__ == '__main__':
    app.run(debug=True)
