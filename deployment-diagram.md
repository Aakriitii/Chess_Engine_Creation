# Chess Engine Deployment Diagram

```mermaid
flowchart TD
    user["User<br/>(Human Player)"]

    computer["Computer Node<br/>Windows Operating System"]

    python["Python Runtime<br/>Python 3.10"]
    app["Chess Application<br/>ChessMain.py"]
    ui["Pygame GUI"]
    engine["Chess Engine Module<br/>ChessEngine.py"]
    ai["AI Module<br/>SmartMoveFinder.py"]
    worker["AI Worker Process<br/>Python multiprocessing"]
    databaseModule["Database Module<br/>Database.py"]
    database[("SQLite Database<br/>chess_games.db")]

    user -->|keyboard and mouse input| ui
    ui -->|runs| app
    app -->|executes in| python
    app -->|uses| engine
    app -->|uses| ai
    app -->|uses| databaseModule
    ai -->|runs search in| worker
    worker -->|executes AI search| ai
    databaseModule -->|reads and writes| database

    subgraph host["Computer Node"]
        python
        app
        ui
        engine
        ai
        worker
        databaseModule
        database
    end
    end
```
