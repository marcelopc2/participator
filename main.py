import streamlit as st
import requests
import pandas as pd
from decouple import config
import time
import io

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

st.set_page_config(page_title="Participation Checker", page_icon="🚀")

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
                    data.append({
                        "Nombre": student.get('user', {}).get('name'),
                        "RUT": student.get('user', {}).get("sis_user_id"),
                        "Correo": student.get('user', {}).get("login_id"),
                        "Ha participado": participation
                    })

                df = pd.DataFrame(data)
                # Guardamos todo en session_state
                st.session_state['df_students'] = df
                st.session_state['tiempo_total'] = tiempo_total
                st.session_state['participantes_count'] = df[df["Ha participado"] == "✔️"].shape[0]
                st.session_state['no_participantes_count'] = df[df["Ha participado"] == "❌"].shape[0]

    # Comprobamos si ya tenemos datos en session_state
    if 'df_students' in st.session_state:
        st.write(f"**Si participaron:** {st.session_state['participantes_count']} / **No participaron:** {st.session_state['no_participantes_count']}")
        st.write(f"")

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
            df_to_show.to_excel(writer, index=False, sheet_name='Datos')
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
