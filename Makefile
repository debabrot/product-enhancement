run-backend:
	uvicorn app.main:app --reload

run-frontend:
	streamlit run frontend/app.py