/**
 * Progress Steps Component
 * Visual progress indicator for multi-step workflows
 * Ported from KA Chat with enhanced styling
 */

export type StepStatus = 'pending' | 'active' | 'completed' | 'failed' | 'waiting';

export interface ProgressStep {
  label: string;
  icon: string;
  status: StepStatus;
}

interface ProgressStepsProps {
  steps: ProgressStep[];
}

export const ProgressSteps = ({ steps }: ProgressStepsProps) => {
  const getStepClass = (status: StepStatus) => {
    return `progress-step-item progress-step-${status}`;
  };

  const getStatusIcon = (status: StepStatus) => {
    switch (status) {
      case 'pending':
        return '⏳';
      case 'active':
        return '⚙️';
      case 'completed':
        return '✅';
      case 'failed':
        return '❌';
      case 'waiting':
        return '⏸️'; // Pause icon for waiting state (user decision required)
    }
  };

  return (
    <div className="progress-steps">
      {steps.map((step, index) => (
        <div key={index} className={getStepClass(step.status)}>
          <div className="step-icon-container">
            <span className="step-icon">{step.icon}</span>
            <span className="step-status-icon">{getStatusIcon(step.status)}</span>
          </div>
          <span className="step-label">{step.label}</span>
          {index < steps.length - 1 && (
            <div className={`step-connector step-connector-${step.status === 'completed' ? 'completed' : 'pending'}`} />
          )}
        </div>
      ))}
    </div>
  );
};