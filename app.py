import streamlit as st
from pathlib import Path

from brochure_generator import generate_brochure

st.set_page_config(
    page_title="AI Brochure Generator",
    page_icon="📄",
    layout="centered"
)

st.title("📄 AI-Powered Company Brochure Generator")
st.write("Generate a marketing brochure from any company website using free LLM APIs (OpenRouter).")

company_name = st.text_input("Company Name", value="HuggingFace")
url = st.text_input("Company Website URL", value="https://huggingface.co")

formats = st.multiselect(
    "Select output formats",
    options=["pdf", "docx", "html"],
    default=["pdf", "docx", "html"]
)

if st.button("Generate Brochure"):
    if not company_name or not url:
        st.error("Please provide both company name and website URL.")
    else:
        with st.spinner("Generating brochure..."):
            try:
                text, file_paths = generate_brochure(company_name, url, formats=formats)

                st.success("Brochure generated successfully!")
                st.subheader("Preview")
                st.markdown(text)

                st.subheader("Download Files")

                for fmt, path in file_paths.items():
                    path = Path(path)
                    mime = {
                        "pdf": "application/pdf",
                        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "html": "text/html",
                    }[fmt]

                    with open(path, "rb") as f:
                        st.download_button(
                            label=f"Download {fmt.upper()}",
                            data=f,
                            file_name=path.name,
                            mime=mime,
                        )

            except Exception as e:
                st.error(f"Error while generating brochure: {e}")
