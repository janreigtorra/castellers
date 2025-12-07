// Scoring utilities

export const calculateSliderScore = (userAnswer, correctAnswer, halfPointMargin) => {
  const diff = Math.abs(userAnswer - correctAnswer);
  
  // Exact match: 100% (1 point)
  if (diff === 0) {
    return 1.0;
  }
  
  // Within margin: proportional between 10% and 90%
  if (diff <= halfPointMargin) {
    // Linear interpolation: 0 diff = 90%, halfPointMargin diff = 10%
    // Formula: 0.9 - (diff / halfPointMargin) * 0.8
    const score = 0.9 - (diff / halfPointMargin) * 0.8;
    return Math.max(0.1, score); // Ensure minimum 10%
  }
  
  // Outside margin: 0% (0 points)
  return 0.0;
};

export const calculateMultipleOptionsScore = (selectedAnswers, correctAnswers) => {
  const correctSet = new Set(correctAnswers);
  
  // Count correct selections (answers that are in both selected and correct)
  const correctSelected = selectedAnswers.filter(ans => correctSet.has(ans)).length;
  
  // Count incorrect selections (answers that are selected but not correct)
  const incorrectSelected = selectedAnswers.filter(ans => !correctSet.has(ans)).length;
  
  // Calculate points: (correct selected / total correct) - penalty for incorrect selections
  // Penalty: subtract half of (incorrect / total correct) but don't go below 0
  const totalCorrect = correctAnswers.length;
  let points = 0;
  
  if (totalCorrect > 0) {
    const correctRatio = correctSelected / totalCorrect;
    const penaltyRatio = (incorrectSelected / totalCorrect) * 0.5; // Half penalty
    points = Math.max(0, correctRatio - penaltyRatio);
  }
  
  return {
    points,
    correctSelected,
    incorrectSelected,
    totalCorrect,
    isPerfect: correctSelected === totalCorrect && incorrectSelected === 0
  };
};

export const calculateOrderingScore = (orderedOptions, correctOrder) => {
  let correctPositions = 0;
  for (let i = 0; i < orderedOptions.length && i < correctOrder.length; i++) {
    if (orderedOptions[i] === correctOrder[i]) {
      correctPositions++;
    }
  }
  
  const totalOptions = correctOrder.length;
  const points = totalOptions > 0 ? correctPositions / totalOptions : 0;
  
  return {
    points,
    correctPositions,
    totalOptions,
    isPerfect: points === 1.0
  };
};

