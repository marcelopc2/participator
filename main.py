import streamlit as st
import requests
import pandas as pd
from decouple import config
import time
import io
from datetime import datetime

# Configuración inicial
BASE_URL = 'https://canvas.uautonoma.cl/api/v1/'
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
            # Verifica si hay más páginas
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

st.set_page_config(page_title="Participation Checker", page_icon="🚀", layout="wide")

def main():
    st.title("Participación en el curso.")
    st.write("Con esta app podras encontrar rapidamente que estudiantes participaron y cuales no en un curso de canvas. Recuerda que puedes ordenar la tabla alfabeticamente o por participacion, asi como puedes filtrar solo por usuarios que NO hayan participado")

    # course_id = st.text_input("Ingrese el ID del curso:", "")
    # ver_participacion = st.button("Ver participación")
    
    with st.form("my_form"):
        course_id = st.text_input("Ingrese el ID del curso:", "")
        ver_participacion = st.form_submit_button("Ver participación")

    # Si el usuario hace clic en "Ver participación"
    if ver_participacion and course_id:
        start_time = time.time()
        with st.spinner("Obteniendo información..."):
            students = get_students(course_id)
            end_time = time.time()
            tiempo_total = end_time - start_time

            if students:
                data = []
                for student in students:
                    participation = check_last_activity(student)
                    created = datetime.strptime(student.get("created_at"), "%Y-%m-%dT%H:%M:%SZ")
                    activity = datetime.strptime(student.get("last_activity_at"), "%Y-%m-%dT%H:%M:%SZ") if student.get("last_activity_at") else None
                    sortable_name_list = student.get('user').get('sortable_name').split(',')
                    rut = student.get('user', {}).get("sis_user_id")
                    data.append({
                        "Nombres": sortable_name_list[1],
                        "Apellidos": sortable_name_list[0],
                        "RUT": f"{rut[:-1]}-{rut[-1]}",
                        "Correo": student.get('user', {}).get("login_id"),
                        "Matriculado": created.strftime("%d-%m-%Y %H:%M"),
                        "Ultima actividad": activity.strftime("%d-%m-%Y %H:%M") if activity else "Nunca",
                        "Ha participado": participation,
                })
                    
                # course_info = get_course_info(course_id)
                # sub_account_info = get_subaccount_info(course_info.get("account_id"))

                df = pd.DataFrame(data)
                # Guardamos todo en session_state
                st.session_state['df_students'] = df
                st.session_state['tiempo_total'] = tiempo_total
                st.session_state['participantes_count'] = df[df["Ha participado"] == "✔️"].shape[0]
                st.session_state['no_participantes_count'] = df[df["Ha participado"] == "❌"].shape[0]
                st.session_state['course_info'] = get_course_info(course_id)
                st.session_state['sub_account_info'] = get_subaccount_info(st.session_state['course_info'].get("account_id"))

    # Comprobamos si ya tenemos datos en session_state
    if 'df_students' in st.session_state:
        diplomado = f"{st.session_state['sub_account_info'].get('name')} - id: {st.session_state['sub_account_info'].get('id')}"
        curso = f"{st.session_state['course_info'].get('name')} - id: {course_id}"
        
        st.markdown(f'<span style="font-size: 28px;">{diplomado}</span>', unsafe_allow_html=True)
        st.markdown(f'<span style="font-size: 22px;">*{curso}*</span>', unsafe_allow_html=True)
        st.markdown(f"**:green[Si participaron:]** {st.session_state['participantes_count']} / **:red[No participaron:]** {st.session_state['no_participantes_count']}")

        mostrar_no_participantes = st.checkbox("Mostrar solo no participantes", value=False)

        if mostrar_no_participantes:
            df_to_show = st.session_state['df_students'][st.session_state['df_students']["Ha participado"] == "❌"]
        else:
            df_to_show = st.session_state['df_students']

        st.dataframe(df_to_show, use_container_width=True)
        st.write(f"**Tiempo de obtención de datos:** {st.session_state['tiempo_total']:.2f} segundos")
        st.write(f"Cuanto tiempo te ahorraste 😉?")

        # Agregar botón de descarga en Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Escribir DataFrame en Excel
            df_to_show.to_excel(writer, index=False, startrow=3, sheet_name='Datos')  # El DataFrame comienza en la fila 4 (startrow=3)

            # Obtener el workbook y worksheet
            workbook = writer.book
            worksheet = writer.sheets['Datos']

            # Agregar título y subtítulo
            title_format = workbook.add_format({'bold': True, 'font_size': 14})
            subtitle_format = workbook.add_format({'italic': True, 'font_size': 12})
            worksheet.write(0, 0, diplomado, title_format)
            worksheet.write(1, 0, curso, subtitle_format)

            # Definir formatos
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

            # Ajustar anchos de columnas con formato centrado
            worksheet.set_column(0, 0, 30)  # Columna 1
            worksheet.set_column(1, 1, 30)  # Columna 2
            worksheet.set_column(2, 2, 15, center_format)  # Columna 3
            worksheet.set_column(3, 3, 40)  # Columna 4
            worksheet.set_column(4, len(df_to_show.columns) - 1, 20, center_format)  # Resto de columnas

            # Obtener el número de filas y columnas del DataFrame
            max_row, max_col = df_to_show.shape

            # Aplicar formato a los encabezados del DataFrame
            for col_num, value in enumerate(df_to_show.columns.values):
                worksheet.write(3, col_num, value, header_format)  # Fila de encabezados en startrow=3

            # Aplicar formato con bordes a cada celda del DataFrame
            for row in range(max_row):
                for col in range(max_col):
                    # La fila en Excel comienza en 4 (startrow=3 + 1) y la columna en 0
                    cell_value = df_to_show.iloc[row, col]
                    worksheet.write(row + 4, col, cell_value, border_format)  # Fila 4 en adelante

        output.seek(0)

        st.download_button(
            label="Descargar un Excel",
            data=output,
            file_name=f'participacion_curso_id_{course_id}.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    elif not course_id and ver_participacion:
        st.error("Por favor, ingrese un ID de curso válido antes de ver la participación.")

if __name__ == "__main__":
    main()
