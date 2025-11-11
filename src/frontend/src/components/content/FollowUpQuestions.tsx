import React from 'react';
import { Button } from '@fluentui/react-components';
import { ChevronRight20Regular } from '@fluentui/react-icons';

interface FollowUpQuestionsProps {
    content: string;
    onQuestionClick: (question: string) => void;
}

/**
 * Component to display follow-up questions extracted from the AI response
 */
export const FollowUpQuestions: React.FC<FollowUpQuestionsProps> = ({ content, onQuestionClick }) => {
    const extractFollowUpQuestions = (text: string): string[] => {
        const questions: string[] = [];
        
        // Match numbered questions like "1. Question text" or "1) Question text"
        const numberedPattern = /^\s*\d+[\.)]\s*(.+?)(?=\n\s*\d+[\.)]|\n\n|$)/gm;
        const matches = text.matchAll(numberedPattern);
        
        for (const match of matches) {
            const question = match[1]?.trim();
            if (question && question.length > 5) {
                questions.push(question);
            }
        }
        
        return questions.slice(0, 3); // Limit to 3 questions
    };

    const questions = extractFollowUpQuestions(content);

    if (questions.length === 0) {
        return null;
    }

    return (
        <div style={{ 
            marginTop: '16px', 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '8px',
            maxWidth: '600px'
        }}>
            {questions.map((question, index) => (
                <Button
                    key={index}
                    appearance="subtle"
                    icon={<ChevronRight20Regular />}
                    iconPosition="before"
                    onClick={() => onQuestionClick(question)}
                    style={{
                        justifyContent: 'flex-start',
                        textAlign: 'left',
                        whiteSpace: 'normal',
                        height: 'auto',
                        minHeight: '32px',
                        padding: '8px 12px'
                    }}
                >
                    {question}
                </Button>
            ))}
        </div>
    );
};
