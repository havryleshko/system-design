'use client'

export default function MolecularLoader() {
  return (
    <div className="molecular-loader">
      <svg width="60" height="60" viewBox="0 0 60 60" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Center node */}
        <circle cx="30" cy="30" r="4" fill="var(--accent)" className="molecule-node center-node" />
        
        {/* Outer ring nodes */}
        <circle cx="30" cy="10" r="3" fill="var(--accent)" className="molecule-node node-1" />
        <circle cx="48" cy="18" r="3" fill="var(--accent)" className="molecule-node node-2" />
        <circle cx="50" cy="38" r="3" fill="var(--accent)" className="molecule-node node-3" />
        <circle cx="30" cy="50" r="3" fill="var(--accent)" className="molecule-node node-4" />
        <circle cx="10" cy="38" r="3" fill="var(--accent)" className="molecule-node node-5" />
        <circle cx="12" cy="18" r="3" fill="var(--accent)" className="molecule-node node-6" />
        
        {/* Connection lines */}
        <line x1="30" y1="30" x2="30" y2="10" stroke="var(--accent)" strokeWidth="1" opacity="0.4" className="molecule-bond bond-1" />
        <line x1="30" y1="30" x2="48" y2="18" stroke="var(--accent)" strokeWidth="1" opacity="0.4" className="molecule-bond bond-2" />
        <line x1="30" y1="30" x2="50" y2="38" stroke="var(--accent)" strokeWidth="1" opacity="0.4" className="molecule-bond bond-3" />
        <line x1="30" y1="30" x2="30" y2="50" stroke="var(--accent)" strokeWidth="1" opacity="0.4" className="molecule-bond bond-4" />
        <line x1="30" y1="30" x2="10" y2="38" stroke="var(--accent)" strokeWidth="1" opacity="0.4" className="molecule-bond bond-5" />
        <line x1="30" y1="30" x2="12" y2="18" stroke="var(--accent)" strokeWidth="1" opacity="0.4" className="molecule-bond bond-6" />
      </svg>
      
      <style jsx>{`
        .molecular-loader {
          display: inline-block;
          position: relative;
        }
        
        @keyframes pulse-node {
          0%, 100% {
            opacity: 0.4;
            r: 3;
          }
          50% {
            opacity: 1;
            r: 4;
          }
        }
        
        @keyframes pulse-center {
          0%, 100% {
            opacity: 0.6;
          }
          50% {
            opacity: 1;
          }
        }
        
        @keyframes pulse-bond {
          0%, 100% {
            opacity: 0.2;
          }
          50% {
            opacity: 0.6;
          }
        }
        
        .center-node {
          animation: pulse-center 2s ease-in-out infinite;
        }
        
        .node-1 {
          animation: pulse-node 2s ease-in-out infinite;
          animation-delay: 0s;
        }
        
        .node-2 {
          animation: pulse-node 2s ease-in-out infinite;
          animation-delay: 0.33s;
        }
        
        .node-3 {
          animation: pulse-node 2s ease-in-out infinite;
          animation-delay: 0.66s;
        }
        
        .node-4 {
          animation: pulse-node 2s ease-in-out infinite;
          animation-delay: 1s;
        }
        
        .node-5 {
          animation: pulse-node 2s ease-in-out infinite;
          animation-delay: 1.33s;
        }
        
        .node-6 {
          animation: pulse-node 2s ease-in-out infinite;
          animation-delay: 1.66s;
        }
        
        .bond-1 {
          animation: pulse-bond 2s ease-in-out infinite;
          animation-delay: 0s;
        }
        
        .bond-2 {
          animation: pulse-bond 2s ease-in-out infinite;
          animation-delay: 0.33s;
        }
        
        .bond-3 {
          animation: pulse-bond 2s ease-in-out infinite;
          animation-delay: 0.66s;
        }
        
        .bond-4 {
          animation: pulse-bond 2s ease-in-out infinite;
          animation-delay: 1s;
        }
        
        .bond-5 {
          animation: pulse-bond 2s ease-in-out infinite;
          animation-delay: 1.33s;
        }
        
        .bond-6 {
          animation: pulse-bond 2s ease-in-out infinite;
          animation-delay: 1.66s;
        }
        
        @media (prefers-reduced-motion: reduce) {
          .molecule-node,
          .molecule-bond,
          .center-node {
            animation: none;
          }
        }
      `}</style>
    </div>
  )
}
