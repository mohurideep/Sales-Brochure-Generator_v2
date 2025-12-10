import streamlit as st
from pathlib import Path

from brochure_generator import generate_brochure, FREE_MODELS,stream_brochure_text

st.set_page_config(
    page_title="AI Brochure Generator",
    page_icon="📄",
    layout="centered"
)

st.title("📄 AI-Powered Company Brochure Generator")
st.write("Generate a marketing brochure from any company website using free LLM APIs (OpenRouter).")

company_name = st.text_input("Company Name", value="HuggingFace")
url = st.text_input("Company Website URL", value="https://huggingface.co")

model_display = st.selectbox(
    "Choose a free LLM model",
    list(FREE_MODELS.keys())  # display user-friendly names
)
selected_pack = FREE_MODELS[model_display] # get the actual model name

formats = st.multiselect(
    "Select output formats",
    options=["pdf", "docx", "html"],
    default=["pdf", "docx", "html"]
)

if st.button("Generate Brochure"):
    if not company_name or not url:
        st.error("Please provide both company name and website URL.")
    else:
        progress = st.progress(0)
        st.info("🔍 Step 1/4: Scraping website & preparing content...")
        progress.progress(20)

        try:
            # Main brochure function
            st.info("🤖 Step 2/4: Generating Brochure Content (live)...")
            progress.progress(40)

            preview_placeholder = st.empty()
            final_text = ""

            # Stream from LLM and update preview live
            for partial_text in stream_brochure_text(company_name, url, selected_pack):
                final_text = partial_text
                preview_placeholder.markdown(final_text)

            st.info("💾 Step 3/4: Saving Brochure Files...")
            progress.progress(70)

            # Reuse streamed text → do NOT call the LLM again
            text, file_paths = generate_brochure(
                company_name,
                url,
                selected_pack,
                formats=formats,
                precomputed_text=final_text
            )

            st.success("📄 Step 4/4: Brochure Ready!")
            progress.progress(100)

            # st.subheader("Preview")
            # st.markdown(text)

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
