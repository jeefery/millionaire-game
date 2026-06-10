"""
Who Wants to Be a Millionaire - Flask Web & Mobile API
Web and mobile-friendly REST API with WebSocket support for real-time interaction
"""

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import os
import json
import random
from datetime import datetime
from typing import Dict, List, Optional
import pyodbc
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['JSON_SORT_KEYS'] = False

# Enable CORS for mobile/web compatibility
CORS(app)

# Initialize SocketIO for real-time communication
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
MSSQL_SERVER = os.getenv('MSSQL_SERVER', 'localhost')
MSSQL_DATABASE = os.getenv('MSSQL_DATABASE', 'MillionaireDB')
MSSQL_USERNAME = os.getenv('MSSQL_USERNAME', 'sa')
MSSQL_PASSWORD = os.getenv('MSSQL_PASSWORD', '')

PRIZE_LEVELS = [100, 200, 500, 1000, 2000, 5000, 10000, 32000, 64000, 125000, 250000, 500000, 1000000]
SAFE_SPOTS = [1000, 32000, 1000000]

# Active game sessions
active_games = {}


class DatabaseManager:
    """MS SQL Server Database Manager"""

    def __init__(self):
        self.connection = None
        self.cursor = None
        self.connected = False
        self.connect()

    def connect(self):
        """Establish database connection"""
        try:
            connection_string = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={MSSQL_SERVER};"
                f"DATABASE={MSSQL_DATABASE};"
                f"UID={MSSQL_USERNAME};"
                f"PWD={MSSQL_PASSWORD}"
            )
            self.connection = pyodbc.connect(connection_string)
            self.cursor = self.connection.cursor()
            self.connected = True
            print("✓ Connected to MS SQL Server")
        except Exception as e:
            print(f"❌ Database connection error: {e}")
            self.connected = False

    def get_random_questions(self, count: int = 13) -> List[Dict]:
        """Get random questions from database"""
        if not self.connected:
            return []

        try:
            query = f"""
                SELECT TOP {count}
                    QuestionID, QuestionText, OptionA, OptionB, OptionC, OptionD,
                    CorrectOption, Difficulty, Category
                FROM Questions
                WHERE IsActive = 1
                ORDER BY NEWID()
            """

            self.cursor.execute(query)
            rows = self.cursor.fetchall()

            questions = []
            for row in rows:
                question = {
                    "id": row[0],
                    "question": row[1],
                    "options": [row[2], row[3], row[4], row[5]],
                    "correct": ord(row[6]) - ord('A'),
                    "difficulty": row[7],
                    "category": row[8]
                }
                questions.append(question)

            return questions
        except Exception as e:
            print(f"❌ Error retrieving questions: {e}")
            return []

    def save_game_session(self, player_name: str, questions_answered: int,
                         final_prize: float, game_won: bool, lifelines: Dict) -> Optional[int]:
        """Save game session to database"""
        if not self.connected:
            return None

        try:
            self.cursor.execute("""
                INSERT INTO GameSessions
                (PlayerName, QuestionsAnswered, FinalPrize, GameWon,
                 LifelineUsed50, LifelineUsedAudience, LifelineUsedPhone)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (player_name, questions_answered, final_prize, game_won,
                  lifelines.get("50:50", False), lifelines.get("ask_audience", False),
                  lifelines.get("phone_friend", False)))

            self.connection.commit()
            self.cursor.execute("SELECT @@IDENTITY")
            session_id = self.cursor.fetchone()[0]
            return int(session_id)
        except Exception as e:
            print(f"❌ Error saving session: {e}")
            return None

    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top players leaderboard"""
        if not self.connected:
            return []

        try:
            self.cursor.execute(f"""
                SELECT TOP {limit}
                    PlayerName, FinalPrize, QuestionsAnswered, GameWon, CreatedDate
                FROM GameSessions
                WHERE GameWon = 1
                ORDER BY FinalPrize DESC, CreatedDate DESC
            """)

            rows = self.cursor.fetchall()
            leaderboard = []
            for i, row in enumerate(rows, 1):
                leaderboard.append({
                    "rank": i,
                    "playerName": row[0],
                    "prize": float(row[1]),
                    "questionsAnswered": row[2],
                    "won": bool(row[3]),
                    "date": row[4].isoformat() if row[4] else None
                })
            return leaderboard
        except Exception as e:
            print(f"❌ Error retrieving leaderboard: {e}")
            return []

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connected = False


# Initialize database
db = DatabaseManager()


# REST API Routes
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "database": "connected" if db.connected else "disconnected",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/game/start', methods=['POST'])
def start_game():
    """Start a new game"""
    try:
        data = request.json
        player_name = data.get('playerName', 'Player')

        # Generate session ID
        session_id = f"session_{random.randint(100000, 999999)}"

        # Load questions from database
        questions = db.get_random_questions(13)

        if not questions:
            return jsonify({
                "success": False,
                "error": "Could not load questions from database"
            }), 500

        # Store game state
        active_games[session_id] = {
            "playerName": player_name,
            "currentLevel": 0,
            "prizeAmount": 0,
            "questions": questions,
            "lifelines": {
                "50:50": False,
                "ask_audience": False,
                "phone_friend": False
            },
            "startTime": datetime.now(),
            "gameOver": False,
            "won": False
        }

        return jsonify({
            "success": True,
            "sessionId": session_id,
            "questions": questions,
            "prizeLevel": PRIZE_LEVELS[0],
            "totalQuestions": len(questions)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@app.route('/api/game/<session_id>/question', methods=['GET'])
def get_current_question(session_id):
    """Get current question"""
    if session_id not in active_games:
        return jsonify({
            "success": False,
            "error": "Session not found"
        }), 404

    game = active_games[session_id]
    current_level = game['currentLevel']

    if current_level >= len(game['questions']):
        return jsonify({
            "success": False,
            "error": "All questions answered"
        }), 400

    question = game['questions'][current_level]

    return jsonify({
        "success": True,
        "questionNumber": current_level + 1,
        "totalQuestions": len(game['questions']),
        "question": question['question'],
        "options": question['options'],
        "category": question['category'],
        "difficulty": question['difficulty'],
        "currentPrize": game['prizeAmount'],
        "nextPrize": PRIZE_LEVELS[current_level] if current_level < len(PRIZE_LEVELS) else 0,
        "lifelines": game['lifelines'],
        "safeSpotsRemaining": [p for p in SAFE_SPOTS if p > game['prizeAmount']]
    })


@app.route('/api/game/<session_id>/answer', methods=['POST'])
def submit_answer(session_id):
    """Submit answer to current question"""
    if session_id not in active_games:
        return jsonify({
            "success": False,
            "error": "Session not found"
        }), 404

    try:
        data = request.json
        answer_index = data.get('answerIndex')

        game = active_games[session_id]
        current_level = game['currentLevel']

        if game['gameOver']:
            return jsonify({
                "success": False,
                "error": "Game is over"
            }), 400

        if current_level >= len(game['questions']):
            return jsonify({
                "success": False,
                "error": "All questions answered"
            }), 400

        question = game['questions'][current_level]
        is_correct = answer_index == question['correct']

        if is_correct:
            game['currentLevel'] += 1
            if game['currentLevel'] < len(PRIZE_LEVELS):
                game['prizeAmount'] = PRIZE_LEVELS[game['currentLevel'] - 1]

            if game['currentLevel'] == len(game['questions']):
                game['won'] = True
                game['gameOver'] = True
                game['prizeAmount'] = PRIZE_LEVELS[-1]

                # Save to database
                db.save_game_session(
                    game['playerName'],
                    game['currentLevel'],
                    game['prizeAmount'],
                    True,
                    game['lifelines']
                )

            return jsonify({
                "success": True,
                "correct": True,
                "nextQuestion": game['currentLevel'] < len(game['questions']),
                "prizeAmount": game['prizeAmount'],
                "won": game['won']
            })
        else:
            game['gameOver'] = True
            game['prizeAmount'] = PRIZE_LEVELS[max(0, game['currentLevel'] - 1)] if game['currentLevel'] > 0 else 0

            # Save to database
            db.save_game_session(
                game['playerName'],
                game['currentLevel'],
                game['prizeAmount'],
                False,
                game['lifelines']
            )

            return jsonify({
                "success": True,
                "correct": False,
                "correctAnswer": chr(ord('A') + question['correct']),
                "prizeAmount": game['prizeAmount'],
                "won": False
            })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@app.route('/api/game/<session_id>/lifeline/<lifeline_type>', methods=['POST'])
def use_lifeline(session_id, lifeline_type):
    """Use a lifeline"""
    if session_id not in active_games:
        return jsonify({
            "success": False,
            "error": "Session not found"
        }), 404

    game = active_games[session_id]

    if lifeline_type not in game['lifelines']:
        return jsonify({
            "success": False,
            "error": "Invalid lifeline"
        }), 400

    if game['lifelines'][lifeline_type]:
        return jsonify({
            "success": False,
            "error": "Lifeline already used"
        }), 400

    current_level = game['currentLevel']
    if current_level >= len(game['questions']):
        return jsonify({
            "success": False,
            "error": "No current question"
        }), 400

    question = game['questions'][current_level]
    correct_index = question['correct']
    options = ['A', 'B', 'C', 'D']

    game['lifelines'][lifeline_type] = True

    if lifeline_type == "50:50":
        wrong_indices = [i for i in range(4) if i != correct_index]
        removed = random.sample(wrong_indices, 2)
        remaining = [options[i] for i in range(4) if i not in removed]

        return jsonify({
            "success": True,
            "lifelineType": "50:50",
            "removed": [options[i] for i in removed],
            "remaining": remaining
        })

    elif lifeline_type == "ask_audience":
        percentages = {}
        if random.random() < 0.82:
            votes = random.randint(48, 82)
            percentages[options[correct_index]] = votes
            remaining = 100 - votes
            for i in range(4):
                if i != correct_index:
                    percentages[options[i]] = remaining // 3
        else:
            for option in options:
                percentages[option] = 25

        return jsonify({
            "success": True,
            "lifelineType": "ask_audience",
            "results": percentages
        })

    elif lifeline_type == "phone_friend":
        if random.random() < 0.75:
            friend_answer = options[correct_index]
            confidence = random.randint(72, 96)
        else:
            friend_answer = random.choice(options)
            confidence = random.randint(35, 65)

        return jsonify({
            "success": True,
            "lifelineType": "phone_friend",
            "friendAnswer": friend_answer,
            "confidence": confidence
        })


@app.route('/api/game/<session_id>/quit', methods=['POST'])
def quit_game(session_id):
    """Quit game and save progress"""
    if session_id not in active_games:
        return jsonify({
            "success": False,
            "error": "Session not found"
        }), 404

    game = active_games[session_id]
    game_prize = PRIZE_LEVELS[max(0, game['currentLevel'] - 1)] if game['currentLevel'] > 0 else 0

    # Save to database
    db.save_game_session(
        game['playerName'],
        game['currentLevel'],
        game_prize,
        False,
        game['lifelines']
    )

    # Clean up session
    del active_games[session_id]

    return jsonify({
        "success": True,
        "finalPrize": game_prize,
        "questionsAnswered": game['currentLevel']
    })


@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """Get leaderboard"""
    limit = request.args.get('limit', 10, type=int)
    leaderboard = db.get_leaderboard(limit)

    return jsonify({
        "success": True,
        "leaderboard": leaderboard
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get game statistics"""
    if not db.connected:
        return jsonify({
            "success": False,
            "error": "Database not connected"
        }), 500

    try:
        db.cursor.execute("""
            SELECT
                COUNT(*) as TotalGames,
                COUNT(CASE WHEN GameWon = 1 THEN 1 END) as GamesWon,
                AVG(CAST(QuestionsAnswered as FLOAT)) as AvgQuestionsAnswered,
                MAX(FinalPrize) as MaxPrize,
                COUNT(DISTINCT PlayerName) as UniquePlayers
            FROM GameSessions
        """)

        row = db.cursor.fetchone()
        stats = {
            "totalGames": row[0] or 0,
            "gamesWon": row[1] or 0,
            "avgQuestionsAnswered": float(row[2]) if row[2] else 0,
            "maxPrize": float(row[3]) if row[3] else 0,
            "uniquePlayers": row[4] or 0
        }

        return jsonify({
            "success": True,
            "stats": stats
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# Web pages
@app.route('/')
def index():
    """Main landing page"""
    return render_template('index.html')


@app.route('/game')
def game():
    """Game page"""
    return render_template('game.html')


@app.route('/leaderboard')
def leaderboard_page():
    """Leaderboard page"""
    return render_template('leaderboard.html')


@app.route('/api/docs')
def api_docs():
    """API documentation"""
    docs = {
        "title": "Who Wants to Be a Millionaire - API Documentation",
        "version": "1.0.0",
        "baseUrl": request.base_url.rstrip('/'),
        "endpoints": {
            "Health Check": {
                "method": "GET",
                "path": "/api/health",
                "description": "Check API and database health"
            },
            "Start Game": {
                "method": "POST",
                "path": "/api/game/start",
                "body": {"playerName": "string"},
                "returns": {"sessionId": "string", "questions": "array"}
            },
            "Get Question": {
                "method": "GET",
                "path": "/api/game/{sessionId}/question",
                "returns": {"question": "string", "options": "array"}
            },
            "Submit Answer": {
                "method": "POST",
                "path": "/api/game/{sessionId}/answer",
                "body": {"answerIndex": "number"},
                "returns": {"correct": "boolean", "prizeAmount": "number"}
            },
            "Use Lifeline": {
                "method": "POST",
                "path": "/api/game/{sessionId}/lifeline/{lifelineType}",
                "params": {"lifelineType": "50:50|ask_audience|phone_friend"},
                "returns": {"success": "boolean"}
            },
            "Quit Game": {
                "method": "POST",
                "path": "/api/game/{sessionId}/quit",
                "returns": {"finalPrize": "number"}
            },
            "Get Leaderboard": {
                "method": "GET",
                "path": "/api/leaderboard",
                "params": {"limit": "number (default: 10)"},
                "returns": {"leaderboard": "array"}
            },
            "Get Statistics": {
                "method": "GET",
                "path": "/api/stats",
                "returns": {"stats": "object"}
            }
        }
    }
    return jsonify(docs)


if __name__ == '__main__':
    # Create required tables if they don't exist
    try:
        db.cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Questions' AND xtype='U')
            CREATE TABLE Questions (
                QuestionID INT PRIMARY KEY IDENTITY(1,1),
                QuestionText NVARCHAR(MAX) NOT NULL,
                OptionA NVARCHAR(500) NOT NULL,
                OptionB NVARCHAR(500) NOT NULL,
                OptionC NVARCHAR(500) NOT NULL,
                OptionD NVARCHAR(500) NOT NULL,
                CorrectOption CHAR(1) NOT NULL,
                Difficulty INT NOT NULL DEFAULT 1,
                Category NVARCHAR(100) NOT NULL DEFAULT 'General',
                CreatedDate DATETIME NOT NULL DEFAULT GETDATE(),
                IsActive BIT NOT NULL DEFAULT 1
            )
        """)

        db.cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='GameSessions' AND xtype='U')
            CREATE TABLE GameSessions (
                SessionID INT PRIMARY KEY IDENTITY(1,1),
                PlayerName NVARCHAR(100),
                StartTime DATETIME NOT NULL DEFAULT GETDATE(),
                EndTime DATETIME,
                QuestionsAnswered INT DEFAULT 0,
                FinalPrize DECIMAL(15,2) DEFAULT 0,
                GameWon BIT DEFAULT 0,
                LifelineUsed50 BIT DEFAULT 0,
                LifelineUsedAudience BIT DEFAULT 0,
                LifelineUsedPhone BIT DEFAULT 0,
                CreatedDate DATETIME NOT NULL DEFAULT GETDATE()
            )
        """)

        db.connection.commit()
    except:
        pass

    # Run the app
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
