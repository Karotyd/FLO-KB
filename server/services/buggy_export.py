"""
Service d'export de conversations
ATTENTION : Ce code contient un bug volontaire pour la leçon de debugging !
"""

def calculate_average_length(messages):
    """
    Calcule la longueur moyenne des messages
    
    Bug volontaire : Division par zéro si la liste est vide
    """
    total_length = 0
    
    for message in messages:
        total_length += len(message)
    
    # BUG ICI : Pas de vérification si messages est vide !
    average = total_length / len(messages)
    
    return average


def export_conversation_summary(session):
    """
    Génère un résumé de conversation
    
    Bug volontaire : Accès à un index qui n'existe pas toujours
    """
    summary = {
        "session_id": session["id"],
        "total_messages": len(session["messages"]),
        "first_message": None,
        "last_message": None,
        "average_length": 0
    }
    
    # BUG ICI : Pas de vérification si messages est vide !
    summary["first_message"] = session["messages"][0]
    summary["last_message"] = session["messages"][-1]
    
    # Calcul de la longueur moyenne
    message_texts = [msg["content"] for msg in session["messages"]]
    summary["average_length"] = calculate_average_length(message_texts)
    
    return summary


def format_export(summary):
    """
    Formate l'export en texte lisible
    
    Bug volontaire : Concaténation de types incompatibles
    """
    output = "=== RÉSUMÉ DE CONVERSATION ===\n"
    output += "Session ID: " + summary["session_id"] + "\n"
    
    # BUG ICI : total_messages est un int, pas une string !
    output += "Nombre de messages: " + summary["total_messages"] + "\n"
    
    output += f"Premier message: {summary['first_message']}\n"
    output += f"Dernier message: {summary['last_message']}\n"
    output += f"Longueur moyenne: {summary['average_length']} caractères\n"
    
    return output


# Script de test
if __name__ == "__main__":
    # Test 1 : Session normale (devrait marcher)
    print("Test 1 : Session normale")
    session1 = {
        "id": "session_123",
        "messages": [
            {"role": "user", "content": "Bonjour"},
            {"role": "assistant", "content": "Bonjour ! Comment puis-je vous aider ?"},
            {"role": "user", "content": "Quelle heure est-il ?"}
        ]
    }
    
    try:
        summary1 = export_conversation_summary(session1)
        result1 = format_export(summary1)
        print(result1)
        print("✓ Test 1 réussi\n")
    except Exception as e:
        print(f"✗ Test 1 échoué : {e}\n")
    
    # Test 2 : Session vide (va planter !)
    print("Test 2 : Session vide")
    session2 = {
        "id": "session_456",
        "messages": []
    }
    
    try:
        summary2 = export_conversation_summary(session2)
        result2 = format_export(summary2)
        print(result2)
        print("✓ Test 2 réussi\n")
    except Exception as e:
        print(f"✗ Test 2 échoué : {e}\n")
    
    # Test 3 : Session avec 1 seul message
    print("Test 3 : Session avec 1 message")
    session3 = {
        "id": "session_789",
        "messages": [
            {"role": "user", "content": "Test"}
        ]
    }
    
    try:
        summary3 = export_conversation_summary(session3)
        result3 = format_export(summary3)
        print(result3)
        print("✓ Test 3 réussi\n")
    except Exception as e:
        print(f"✗ Test 3 échoué : {e}\n")