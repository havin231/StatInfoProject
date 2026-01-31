from app import create_app

# Create an instance of the application using the factory function
app = create_app()

if __name__ == '__main__':
    # --- DEVELOPMENT SERVER ---
    # Running in debug mode allows you to see errors directly in the browser
    # and automatically reloads the server when you modify code.
    # WARNING: Do not use debug=True in a production environment.
    app.run(debug=True)
