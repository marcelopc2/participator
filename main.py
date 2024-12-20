import streamlit as st
import requests
import pandas as pd
from decouple import config
import time
import io
from datetime import datetime
from unidecode import unidecode

# Configuración inicial
BASE_URL = 'https://canvas.uautonoma.cl/api/v1'
TOKEN = config("TOKEN")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def get_students(course_id):
    url = f"{BASE_URL}/courses/{course_id}/enrollments"
    params = {"type[]": "StudentEnrollment", "per_page": 100}
    students = []
    while url:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 200:
            students.extend(response.json())
            url = response.links.get('next', {}).get('url')
        else:
            st.error(f"Error {response.status_code}: No se pudo obtener la lista de estudiantes.")
            break
    return students

def check_last_activity(student):
    last_activity = student.get("last_activity_at")
    return '✔️' if last_activity else '❌'

def get_course_info(course_id):
    response = requests.get(f"{BASE_URL}/courses/{course_id}", headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error {response.status_code}: No se pudo obtener la información del curso.")
        return None
    
def get_subaccount_info(sub_account_id):
    response = requests.get(f"{BASE_URL}/accounts/{sub_account_id}", headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error {response.status_code}: No se pudo obtener la información de la subcuenta.")
        return None

def get_assignments(course_id):
    assignments = []
    url = f"{BASE_URL}/courses/{course_id}/assignments"
    while url:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            assignments.extend(data)
            if 'next' in response.links:
                url = response.links['next']['url']
            else:
                url = None
        else:
            st.error(f"Error {response.status_code} al obtener tareas: {response.text}")
            return []
    return assignments

def get_submissions(course_id, assignment_id):
    submissions = []
    url = f"{BASE_URL}/courses/{course_id}/assignments/{assignment_id}/submissions?per_page=100"
    while url:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            submissions.extend(data)
            if 'next' in response.links:
                url = response.links['next']['url']
            else:
                url = None
        else:
            st.error(f"Error {response.status_code} al obtener entregas: {response.text}")
            return []
    return submissions

st.set_page_config(page_title="Participation Checker", page_icon="🚀", layout="wide")

def main():
    st.title("Participación en el curso.")
    st.write("Con esta app podrás encontrar rápidamente qué estudiantes participaron y cuáles no en un curso de Canvas. Puedes además opcionalmente incluir las columnas para las tareas (excluyendo las autoevaluaciones).")

    with st.form("my_form"):
        course_id = st.text_input("Ingrese el ID del curso:", "")
        include_assignments = st.checkbox("Incluir entregas en tareas", value=False)
        ver_participacion = st.form_submit_button("Ver participación")

    if ver_participacion and course_id:
        start_time = time.time()  # Se define start_time aquí
        with st.spinner("Obteniendo información..."):
            students = get_students(course_id)

            if students:
                data = []
                for student in students:
                    participation = check_last_activity(student)
                    created = datetime.strptime(student.get("created_at"), "%Y-%m-%dT%H:%M:%SZ")
                    activity = datetime.strptime(student.get("last_activity_at"), "%Y-%m-%dT%H:%M:%SZ") if student.get("last_activity_at") else None
                    sortable_name_list = student.get('user').get('sortable_name').split(',')
                    rut = student.get('user', {}).get("sis_user_id")
                    user_id = student.get('user', {}).get('id')
                    data.append({
                        "Nombres": sortable_name_list[1].strip(),
                        "Apellidos": sortable_name_list[0].strip(),
                        "RUT": f"{rut[:-1]}-{rut[-1]}" if rut else None,
                        "Correo": student.get('user', {}).get("login_id"),
                        "Matriculado": created.strftime("%d-%m-%Y %H:%M"),
                        "Ultima actividad": activity.strftime("%d-%m-%Y %H:%M") if activity else "Nunca",
                        "Ha participado": participation,
                        "user_id": user_id
                    })
                    
                df = pd.DataFrame(data)

                # Obtener información del curso y subcuenta
                course_info = get_course_info(course_id)
                sub_account_info = get_subaccount_info(course_info.get("account_id"))

                # Si se incluye la opción de buscar tareas y entregas
                if include_assignments:
                    assignments = get_assignments(course_id)
                    filtered_assignments = []
                    for a in assignments:
                        normalized_name = unidecode(a['name'].lower())
                        if 'autoevaluacion' not in normalized_name:
                            filtered_assignments.append(a)

                    assignment_submissions = {}
                    for a in filtered_assignments:
                        submissions = get_submissions(course_id, a['id'])
                        delivered = set()
                        for s in submissions:
                            wfs = s.get('workflow_state')
                            grd = s.get('grade')
                            # Consideramos "Entregado" si:
                            # workflow_state in ['submitted', 'graded'] y grade > 0
                            if wfs in ['submitted', 'graded']:
                                if grd is not None:
                                    try:
                                        if float(grd) > 0:
                                            delivered.add(s['user_id'])
                                    except:
                                        delivered.add(s['user_id'])
                                else:
                                    delivered.add(s['user_id'])

                        assignment_submissions[a['id']] = (a['name'], delivered)

                    for a_id, (a_name, submitted_ids) in assignment_submissions.items():
                        df[a_name] = df['user_id'].apply(lambda uid: "✔️" if uid in submitted_ids else "❌")

                # Aquí calculamos end_time y tiempo_total inmediatamente después de obtener y procesar todos los datos
                end_time = time.time()
                tiempo_total = end_time - start_time

                # Guardamos todo en session_state, incluido el tiempo total
                st.session_state['df_students'] = df
                st.session_state['tiempo_total'] = tiempo_total
                st.session_state['participantes_count'] = df[df["Ha participado"] == "✔️"].shape[0]
                st.session_state['no_participantes_count'] = df[df["Ha participado"] == "❌"].shape[0]
                st.session_state['course_info'] = course_info
                st.session_state['sub_account_info'] = sub_account_info
                st.session_state['include_assignments'] = include_assignments

    if 'df_students' in st.session_state:
        diplomado = f"{st.session_state['sub_account_info'].get('name')} - id: {st.session_state['sub_account_info'].get('id')}"
        curso = f"{st.session_state['course_info'].get('name')} - id: {st.session_state['course_info'].get('id')}"

        st.markdown(f'<span style="font-size: 28px;">{diplomado}</span>', unsafe_allow_html=True)
        st.markdown(f'<span style="font-size: 22px;">*{curso}*</span>', unsafe_allow_html=True)
        st.markdown(f"**:green[Si participaron:]** {st.session_state['participantes_count']} / **:red[No participaron:]** {st.session_state['no_participantes_count']}")

        mostrar_no_participantes = st.checkbox("Mostrar solo no participantes", value=False)

        df = st.session_state['df_students']
        if mostrar_no_participantes:
            df_to_show = df[df["Ha participado"] == "❌"]
        else:
            df_to_show = df

        # Ocultamos la columna user_id de la vista
        if 'user_id' in df_to_show.columns:
            df_to_show = df_to_show.drop(columns=['user_id'])

        st.dataframe(df_to_show, use_container_width=True)

        # Aquí ya leemos el tiempo desde session_state
        st.write(f"**Tiempo de obtención de datos:** {st.session_state['tiempo_total']:.2f} segundos")
        st.write("¿Cuánto tiempo te ahorraste 😉?")

        # Botón de descarga en Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_to_show.to_excel(writer, index=False, startrow=3, sheet_name='Datos')
            workbook = writer.book
            worksheet = writer.sheets['Datos']

            title_format = workbook.add_format({'bold': True, 'font_size': 14})
            subtitle_format = workbook.add_format({'italic': True, 'font_size': 12})
            worksheet.write(0, 0, diplomado, title_format)
            worksheet.write(1, 0, curso, subtitle_format)

            center_format = workbook.add_format({'align': 'center'})
            border_format = workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'border': 1
            })
            check_format = workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_color': 'green'
            })
            cross_format = workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'font_color': 'red'
            })

            worksheet.set_column(0, 0, 30) 
            worksheet.set_column(1, 1, 30) 
            worksheet.set_column(2, 2, 15, center_format)
            worksheet.set_column(3, 3, 40)
            worksheet.set_column(4, len(df_to_show.columns) - 1, 20, center_format)

            max_row, max_col = df_to_show.shape

            for col_num, value in enumerate(df_to_show.columns.values):
                worksheet.write(3, col_num, value, header_format)

            for row in range(max_row):
                for col in range(max_col):
                    cell_value = df_to_show.iloc[row, col]
                    excel_row = row + 4
                    excel_col = col
                    if cell_value == '✔️':
                        cell_format = check_format
                    elif cell_value == '❌':
                        cell_format = cross_format
                    else:
                        cell_format = border_format
                    worksheet.write(excel_row, excel_col, cell_value, cell_format)

            worksheet.set_default_row(20)

        output.seek(0)
        st.download_button(
            label="Descargar un Excel",
            data=output,
            file_name=f'participacion_curso_id_{st.session_state["course_info"].get("id")}.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    elif ver_participacion and not course_id:
        st.error("Por favor, ingrese un ID de curso válido antes de ver la participación.")

if __name__ == "__main__":
    main()
