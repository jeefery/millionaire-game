#!/usr/bin/env python3
"""
Who Wants to Be a Millionaire - Azure AI Voice Interactive Game
A command-line implementation with Azure Cognitive Services voice interaction
"""

import random
import time
from typing import List, Tuple, Dict
import os
import sys
import json

# Try importing Azure libraries
try:
    import azure.cognitiveservices.speech as speechsdk
    AZURE_SPEECH_AVAILABLE = True
except ImportError:
    AZURE_SPEECH_AVAILABLE = False
    print("Warning: Azure Speech SDK not installed. Install with: pip install azure-cognitiveservices-speech")

# Prize levels in ascending order
PRIZE_LEVELS = [
    100,
    200,
    500,
    1000,
    2000,
    5000,
    10000,
    32000,
    64000,
    125000,
    250000,
    500000,
    1000000,
]

# Safe spots (amounts that are guaranteed)
SAFE_SPOTS = [0, 1000, 32000, 250000, 1000000]

# Lifelines
LIFELINES = {
    "50:50": "Remove two wrong answers",
    "ask_audience": "Ask the audience",
    "phone_friend": "Call a friend",
}

# Quiz questions with multiple choice answers
QUESTIONS = [
    {
        "question": "What is the capital of France?",
        "options": ["A) London", "B) Berlin", "C) Paris", "D) Madrid"],
        "correct": "C",
        "difficulty": 1,
    },
    {
        "question": "Which planet is known as the Red Planet?",
        "options": ["A) Venus", "B) Mars", "C) Jupiter", "D) Saturn"],
        "correct": "B",
        "difficulty": 1,
    },
    {
        "question": "What is the largest ocean on Earth?",
        "options": [
            "A) Atlantic Ocean",
            "B) Indian Ocean",
            "C) Arctic Ocean",
            "D) Pacific Ocean",
        ],
        "correct": "D",
        "difficulty": 1,
    },
    {
        "question": "Who wrote 'Romeo and Juliet'?",
        "options": [
            "A) Charles Dickens",
            "B) William Shakespeare",
            "C) Jane Austen",
            "D) Mark Twain",
        ],
        "correct": "B",
        "difficulty": 2,
    },
    {
        "question": "What is the smallest prime number?",
        "options": ["A) 0", "B) 1", "C) 2", "D) 3"],
        "correct": "C",
        "difficulty": 2,
    },
    {
        "question": "In what year did the Titanic sink?",
        "options": ["A) 1912", "B) 1920", "C) 1905", "D) 1915"],
        "correct": "A",
        "difficulty": 2,
    },
    {
        "question": "What is the chemical symbol for Gold?",
        "options": ["A) Go", "B) Gd", "C) Au", "D) Ag"],
        "correct": "C",
        "difficulty": 3,
    },
    {
        "question": "Which country is home to the kangaroo?",
        "options": ["A) New Zealand", "B) Australia", "C) South Africa", "D) Brazil"],
        "correct": "B",
        "difficulty": 2,
    },
    {
        "question": "What is the speed of light?",
        "options": [
            "A) 300,000 km/s",
            "B) 150,000 km/s",
            "C) 500,000 km/s",
            "D) 100,000 km/s",
        ],
        "correct": "A",
        "difficulty": 3,
    },
    {
        "question": "How many strings does a violin have?",
        "options": ["A) 4", "B) 6", "C) 8", "D) 10"],
        "correct": "A",
        "difficulty": 2,
    },
    {
        "question": "What is the most spoken language in the world?",
        "options": ["A) Spanish", "B) English", "C) Mandarin Chinese", "D) Hindi"],
        "correct": "C",
        "difficulty": 2,
    },
    {
        "question": "In what year did World War II end?",
        "options": ["A) 1943", "B) 1944", "C) 1945", "D) 1946"],
        "correct": "C",
        "difficulty": 2,
    },
    {
        "question": "What is the largest mammal in the world?",
        "options": ["A) African Elephant", "B) Blue Whale", "C) Giraffe", "D) Hippopotamus"],
        "correct": "B",
        "difficulty": 1,
    },
    {
        "question": "Which element has the atomic number 1?",
        "options": ["A) Helium", "B) Hydrogen", "C) Lithium", "D) Beryllium"],
        "correct": "B",
        "difficulty": 2,
    },
    {
        "question": "What is the Great Wall of China made of primarily?",
        "options": ["A) Stone", "B) Brick", "C) Wood", "D) Concrete"],
        "correct": "A",
        "difficulty": 2,
    },
]


class AzureVoiceEngine:
    """Handles Azure Cognitive Services text-to-speech and speech recognition"""

    def __init__(self, speech_key: str, speech_region: str, language: str = "en-US"):
        """
        Initialize Azure Voice Engine
        
        Args:
            speech_key: Azure Speech API key
            speech_region: Azure region (e.g., 'eastus', 'westus')
            language: Language code (default: 'en-US')
        """
        self.speech_key = speech_key
        self.speech_region = speech_region
        self.language = language
        self.speech_config = None
        self.recognizer = None
        self.synthesizer = None
        self.initialized = False

        try:
            # Initialize speech config
            self.speech_config = speechsdk.SpeechConfig(
                subscription=speech_key, region=speech_region
            )
            self.speech_config.speech_recognition_language = language

            # Initialize recognizer (from microphone)
            audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
            self.recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config, audio_config=audio_config
            )

            # Initialize synthesizer (to speakers)
            self.synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config, audio_config=speechsdk.audio.AudioConfig(use_default_speaker=True)
            )

            # Set voice characteristics
            self.speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"

            self.initialized = True
            print("✓ Azure Speech Services initialized successfully!")

        except Exception as e:
            print(f"Error initializing Azure Speech Services: {e}")
            self.initialized = False

    def speak(self, text: str):
        """Convert text to speech using Azure"""
        if not self.initialized or not self.synthesizer:
            print(f"Text: {text}")
            return

        try:
            print(f"🔊 Speaking: {text}")
            result = self.synthesizer.speak_text_async(text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print("✓ Speech synthesis completed")
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                print(f"Speech synthesis canceled: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    print(f"Error details: {cancellation_details.error_details}")

        except Exception as e:
            print(f"Error in text-to-speech: {e}")

    def listen(self, timeout: int = 5) -> str:
        """Listen to microphone and convert to text using Azure"""
        if not self.initialized or not self.recognizer:
            return ""

        try:
            print("🎤 Listening... (speak now)")
            result = self.recognizer.recognize_once_async().get()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                text = result.text
                print(f"You said: {text}")
                return text.strip().upper()

            elif result.reason == speechsdk.ResultReason.NoMatch:
                print("Could not understand audio. Please try again.")
                return ""

            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                print(f"Speech recognition canceled: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    print(f"Error details: {cancellation_details.error_details}")
                return ""

        except Exception as e:
            print(f"Error in speech recognition: {e}")
            return ""

    def get_available_voices(self) -> List[str]:
        """Get list of available neural voices"""
        # Common Azure neural voices
        return [
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-US-JennyNeural",
            "en-GB-LibbyNeural",
            "en-AU-NatashaNeural",
        ]

    def set_voice(self, voice_name: str):
        """Set the voice for speech synthesis"""
        if not self.initialized or not self.speech_config:
            return

        try:
            self.speech_config.speech_synthesis_voice_name = voice_name
            print(f"✓ Voice set to: {voice_name}")
        except Exception as e:
            print(f"Error setting voice: {e}")

    def close(self):
        """Clean up resources"""
        try:
            if self.recognizer:
                self.recognizer.close()
            if self.synthesizer:
                self.synthesizer.close()
        except:
            pass


class MillionaireGame:
    def __init__(self, use_voice: bool = True, speech_key: str = None, speech_region: str = None):
        self.current_level = 0
        self.prize_money = 0
        self.lifelines_used = {key: False for key in LIFELINES.keys()}
        self.current_question = None
        self.questions_answered = 0
        self.game_over = False
        self.won = False
        self.use_voice = use_voice
        self.voice_engine = None

        if use_voice and speech_key and speech_region:
            self.voice_engine = AzureVoiceEngine(speech_key, speech_region)
            if not self.voice_engine.initialized:
                self.use_voice = False
                print("Voice interaction disabled due to initialization error")
        elif use_voice:
            print("Warning: Azure Speech API credentials not provided")
            self.use_voice = False

    def speak(self, text: str):
        """Speak text if voice is enabled"""
        if self.use_voice and self.voice_engine:
            self.voice_engine.speak(text)
        else:
            print(f"🔊 {text}")

    def listen(self) -> str:
        """Listen for user input if voice is enabled"""
        if self.use_voice and self.voice_engine:
            return self.voice_engine.listen()
        return ""

    def display_welcome(self):
        """Display welcome message"""
        welcome_text = """Welcome to Who Wants to Be a Millionaire!
        
Rules:
- Answer 13 questions correctly to win 1 million dollars
- Each wrong answer ends the game
- You have 3 lifelines: 50-50, Ask Audience, and Phone Friend
- Say your answer as A, B, C, or D, or say a lifeline name

Prize Levels: 100, 200, 500, 1000, 2000, 5000, 10000, 32000, 64000, 125000, 250000, 500000, and 1 million dollars!

Good luck!"""

        print("\n" + "=" * 60)
        print("       WELCOME TO WHO WANTS TO BE A MILLIONAIRE?       ")
        print("=" * 60)
        print(welcome_text)
        print("=" * 60 + "\n")

        self.speak(
            "Welcome to Who Wants to Be a Millionaire! "
            "Answer 13 questions to win one million dollars. Good luck!"
        )

    def display_current_status(self):
        """Display current prize and question number"""
        safe_money = 0
        for safe_spot in SAFE_SPOTS:
            if self.prize_money <= safe_spot:
                safe_money = safe_spot
                break

        print(f"\n{'Current Prize:':.<30} ${self.prize_money:,}")
        print(f"{'Guaranteed (Safe Spot):':.<30} ${safe_money:,}")
        print(f"{'Question:':.<30} {self.current_level + 1}/13")
        print()

    def display_lifelines_status(self):
        """Display available lifelines"""
        print("Available Lifelines:")
        for key, value in LIFELINES.items():
            status = "✓ USED" if self.lifelines_used[key] else "○"
            print(f"  {status} {key}: {value}")
        print()

    def ask_audience(self, correct_answer: str) -> Dict[str, int]:
        """Simulate audience voting"""
        options = ["A", "B", "C", "D"]
        percentages = {}

        if random.random() < 0.8:
            votes = random.randint(45, 75)
            percentages[correct_answer] = votes
            remaining = 100 - votes
            for option in options:
                if option != correct_answer:
                    percentages[option] = remaining // 3
        else:
            for option in options:
                percentages[option] = 25

        return percentages

    def phone_friend(self, correct_answer: str) -> Tuple[str, int]:
        """Simulate calling a friend"""
        options = ["A", "B", "C", "D"]

        if random.random() < 0.7:
            chosen_answer = correct_answer
            confidence = random.randint(70, 95)
        else:
            chosen_answer = random.choice(options)
            confidence = random.randint(40, 70)

        return chosen_answer, confidence

    def use_lifeline(self, lifeline: str, correct_answer: str):
        """Use a lifeline"""
        if self.lifelines_used[lifeline]:
            message = f"You have already used {lifeline}!"
            print(f"\n{message}")
            self.speak(message)
            return

        self.lifelines_used[lifeline] = True

        if lifeline == "50:50":
            options = ["A", "B", "C", "D"]
            wrong_options = [opt for opt in options if opt != correct_answer]
            removed = random.sample(wrong_options, 2)
            remaining = [opt for opt in options if opt not in removed]

            message = f"Using 50 50. Removing options {' and '.join(removed)}. Remaining options are {' and '.join(remaining)}"
            print(f"\n50:50: Removing two incorrect answers...")
            print(f"Remaining options: {', '.join(remaining)}")
            self.speak(message)

        elif lifeline == "ask_audience":
            percentages = self.ask_audience(correct_answer)
            print(f"\nAudience Voting Results:")
            msg_parts = ["Audience voting results: "]
            for option in ["A", "B", "C", "D"]:
                pct = percentages[option]
                print(f"  {option}: {pct:>2}%")
                msg_parts.append(f"Option {option}: {pct} percent. ")
            self.speak("".join(msg_parts))

        elif lifeline == "phone_friend":
            answer, confidence = self.phone_friend(correct_answer)
            message = f"Your friend thinks the answer is {answer} with {confidence} percent confidence"
            print(f"\nYour friend thinks the answer is {answer}")
            print(f"Confidence level: {confidence}%")
            self.speak(message)

    def get_question(self) -> Dict:
        """Get next question"""
        if self.current_level < len(QUESTIONS):
            return QUESTIONS[self.current_level]
        return None

    def ask_question(self):
        """Ask current question and get answer"""
        question_data = self.get_question()

        if not question_data:
            self.won = True
            self.game_over = True
            return

        self.display_current_status()

        # Speak the question
        question_text = question_data["question"]
        print(f"Question {self.current_level + 1}:")
        print(question_text)
        print()

        self.speak(f"Question {self.current_level + 1}. {question_text}")

        # Speak the options
        for option in question_data["options"]:
            print(option)

        options_text = " ".join(question_data["options"])
        self.speak(f"Your options are: {options_text}")
        print()

        while True:
            self.display_lifelines_status()

            # Get user input
            if self.use_voice:
                print("Say your answer (A, B, C, D) or a lifeline:")
                user_input = self.listen()
                if not user_input:
                    print("Sorry, I didn't catch that. Please try again.")
                    self.speak("Sorry, I did not understand. Please try again.")
                    continue
            else:
                user_input = input("Your answer (A/B/C/D) or lifeline (50:50/audience/phone): ").strip().upper()

            # Parse input
            if user_input in ["A", "B", "C", "D"]:
                return user_input
            elif user_input == "50:50":
                self.use_lifeline("50:50", question_data["correct"])
            elif user_input in ["AUDIENCE", "ASK_AUDIENCE"]:
                self.use_lifeline("ask_audience", question_data["correct"])
            elif user_input in ["PHONE", "PHONE_FRIEND"]:
                self.use_lifeline("phone_friend", question_data["correct"])
            else:
                print("Invalid input. Please enter A, B, C, D or a lifeline name.\n")
                self.speak("Invalid input. Please say a letter or a lifeline.")

    def check_answer(self, answer: str) -> bool:
        """Check if answer is correct"""
        question_data = self.get_question()
        return answer == question_data["correct"]

    def update_prize(self):
        """Update prize money based on current level"""
        if self.current_level < len(PRIZE_LEVELS):
            self.prize_money = PRIZE_LEVELS[self.current_level]

    def play_round(self):
        """Play a single round"""
        answer = self.ask_question()

        if self.game_over:  # Already won
            return

        if self.check_answer(answer):
            message = f"Correct answer! You have won ${self.prize_money:,}"
            print(f"\n✓ Correct Answer!")
            print(message)
            self.speak("Correct!")
            self.current_level += 1
            self.update_prize()
            time.sleep(1)

            if self.current_level == len(PRIZE_LEVELS):
                self.won = True
                self.game_over = True
        else:
            correct = self.get_question()["correct"]
            safe_amount = PRIZE_LEVELS[max(0, self.current_level - 1)] if self.current_level > 0 else 0
            message = f"Wrong answer! The correct answer was {correct}. You won ${safe_amount:,}"
            print(f"\n✗ Wrong Answer! The correct answer was {correct}")
            print(message)
            self.speak(message)
            self.game_over = True

    def display_final_screen(self):
        """Display final game screen"""
        print("\n" + "=" * 60)
        if self.won:
            print("🎉 CONGRATULATIONS! YOU'VE WON $1,000,000! 🎉")
            message = "Congratulations! You have won one million dollars!"
        else:
            print("Game Over!")
            print(f"You answered {self.current_level} questions correctly")
            message = f"Game over. You won ${self.prize_money:,}. Better luck next time!"

        print("=" * 60)
        print(f"Final Prize: ${self.prize_money:,}")
        print("=" * 60 + "\n")

        self.speak(message)

    def play(self):
        """Main game loop"""
        self.display_welcome()

        while not self.game_over:
            self.play_round()

        self.display_final_screen()

    def cleanup(self):
        """Clean up resources"""
        if self.voice_engine:
            self.voice_engine.close()


def load_azure_credentials() -> Tuple[str, str]:
    """Load Azure Speech API credentials"""
    # Try to load from environment variables
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION")

    if speech_key and speech_region:
        print(f"✓ Loaded Azure credentials from environment")
        return speech_key, speech_region

    # Try to load from config file
    config_file = "azure_credentials.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
            speech_key = config.get("speech_key")
            speech_region = config.get("speech_region")
            if speech_key and speech_region:
                print(f"✓ Loaded Azure credentials from {config_file}")
                return speech_key, speech_region
        except Exception as e:
            print(f"Error reading {config_file}: {e}")

    # Prompt user
    print("\nAzure Speech API credentials required for voice interaction:")
    speech_key = input("Enter your Azure Speech API Key: ").strip()
    speech_region = input("Enter your Azure Speech Region (e.g., 'eastus'): ").strip()

    # Optionally save credentials
    if input("Save credentials? (yes/no): ").strip().lower() in ["yes", "y"]:
        try:
            with open(config_file, "w") as f:
                json.dump({"speech_key": speech_key, "speech_region": speech_region}, f)
            print(f"✓ Credentials saved to {config_file}")
        except Exception as e:
            print(f"Error saving credentials: {e}")

    return speech_key, speech_region


def setup_azure_services():
    """Check and provide instructions for Azure setup"""
    print("\n" + "=" * 60)
    print("AZURE SPEECH SERVICES SETUP")
    print("=" * 60)

    if not AZURE_SPEECH_AVAILABLE:
        print("\n❌ Azure Cognitive Services SDK not found")
        print("Install with: pip install azure-cognitiveservices-speech")
        print("\nAlso install other required packages:")
        print("pip install python-dotenv")
        return False

    print("\n✓ Azure Cognitive Services SDK installed")

    print("\nTo use Azure Speech Services:")
    print("1. Create an Azure account at https://azure.microsoft.com")
    print("2. Create a Speech resource in the Azure Portal")
    print("3. Get your API Key and Region from the resource")
    print("4. Set environment variables or use credentials file:")
    print("   - AZURE_SPEECH_KEY")
    print("   - AZURE_SPEECH_REGION")
    print("\nOr create an 'azure_credentials.json' file with:")
    print('   {"speech_key": "YOUR_KEY", "speech_region": "YOUR_REGION"}')

    return True


def main():
    """Entry point"""
    print("\n" + "=" * 60)
    print("WHO WANTS TO BE A MILLIONAIRE - AZURE AI VOICE EDITION")
    print("=" * 60)

    # Check for Azure setup
    if not setup_azure_services():
        use_voice_input = input("\nContinue without voice? (yes/no): ").strip().lower() in [
            "yes",
            "y",
        ]
        if not use_voice_input:
            print("Please install Azure Cognitive Services SDK and try again.")
            return
        use_voice = False
    else:
        use_voice = input("\nDo you want to use voice interaction? (yes/no): ").strip().lower() in [
            "yes",
            "y",
        ]

    speech_key = None
    speech_region = None

    if use_voice:
        speech_key, speech_region = load_azure_credentials()

    game = MillionaireGame(use_voice=use_voice, speech_key=speech_key, speech_region=speech_region)
    game.play()

    while True:
        if game.use_voice:
            print("\nSay 'yes' to play again or 'no' to quit:")
            response = game.listen()
            play_again = response.lower() if response else ""
        else:
            play_again = input("\nWould you like to play again? (yes/no): ").strip().lower()

        if play_again in ["yes", "y"]:
            game = MillionaireGame(use_voice=use_voice, speech_key=speech_key, speech_region=speech_region)
            game.play()
        elif play_again in ["no", "n"]:
            print("Thanks for playing! Goodbye!")
            if game.use_voice:
                game.speak("Thanks for playing! Goodbye!")
            game.cleanup()
            break
        else:
            print("Please say or enter 'yes' or 'no'.")


if __name__ == "__main__":
    main()
