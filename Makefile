run-backend:
	uvicorn app.main:app --reload

run-frontend:
	streamlit run app/app.py