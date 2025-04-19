from core.agent import ToolCallingAgent
from tools import (
    login,
    getUnclassifiedEmails,
    getUnreadUnclassifiedEmails,
    getExistingLabels,
    createLabels,
    deleteLabels,
    sortEmails
)

Agent = ToolCallingAgent(
    [login, getUnclassifiedEmails, getUnreadUnclassifiedEmails, getExistingLabels, createLabels, deleteLabels, sortEmails],
    persistent_prompt="""You are a personal assistant tasked with classifying emails.
    Don't hesitate to make multiple tool calls at once, or classify multiple emails at once for efficiency.
    As a rule of thumb, you should never create a label just for one email. Be very conservative in creating label, optimally, you should create none and assume that the existing ones are enough.
    Don't try to get too many emails at once, retrieve batches of 10, or even less if you deem it necessary.""",
    max_steps=500
)

if __name__ == "__main__":
    print("Welcome to the Email Agent!")
    print("""                                                              
  
                               @                               
                             @@@@@                             
                              @@@                              
                               @                               
                       @@@@@@@@@@@@@@@@@                       
                   @@@@                 @@@@                   
                  @@                       @@                  
                 @                           @                 
               @@@                           @@@               
              @@@      @@@@         @@@@     @@@@              
              @@@      @@@@         @@@@      @@@              
              @@@       @@           @@      @@@@              
              @@@@         @       @         @@@@              
                @@          @@@@@@@          @@                
                 @@                         @@                 
                   @@@@                 @@@@                   
                        @@@@@@@@@@@@@@@                        
                  @@@@@@@@@@@@@@@@@@@@@@@@@@@                  
              @@@@                           @@@@              
            @@  @@ @@@@@@@@@@@@@@@@@@@@@@@@@ @@  @@            
           @@@  @@ @@@                   @@@ @@  @@@           
          @@  @@@@ @@ @@@             @@@ @@ @@@@  @@          
         @@    @@@ @@    @@         @@    @@ @@@    @@         
         @@@@@@@@@@@@@     @@     @@     @@@@@@@@@@@@@         
         @@    @@     @@  @@ @@ @@ @@  @@     @@    @@         
         @    @@     @@ @@           @@ @@     @@    @         
         @@   @@     @@@               @@@     @@   @@         
            @@@@@@@@@@                   @@@@@@@@@@            
                @@ @@@@@@@@@@@@@@@@@@@@@@@@@ @@                
                 @                           @                 
                  @@@                     @@@                  
                                                                                
""")
    print("I'll sort emails lying around in your inbox, either only the unread ones or all of them. Just tell me how many you need me to sort, and what I should focus on!")
    prompt = input("Prompt: ")
    results = Agent.run(prompt)
    print(results)