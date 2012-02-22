require 'sinatra'
require 'sinatra/reloader' if development?

#set :port, 2222
set :logging, true

@nodes = (1..7)

helpers do
  def setup
    @nodes = {} 
    (1..7).each do |i|
      @nodes[i] = [i, "Node #{i}", "node#{i}.lab.msp.redhat.com"]
    end
    @cur_node = params[:node].to_i
    if @cur_node == 0 then
      @cur_node = @nodes[1]
    else
      @cur_node = @nodes[@cur_node]
    end
  end
end

get '/blah' do
  print "blah"
  erb "Blah!"
end

get '/resourcedeps/?:resource?' do
  setup()
  @resourcedepsmenuclass = "class=\"active\""
  erb :index
end

get '/resources/?:resource?' do
  setup()
  @resourcemenuclass = "class=\"active\""
  erb :index
end

get '/nodes/?:node?' do
  print "Nodes\n"
  setup()
  @nodemenuclass = "class=\"active\""
  erb :index
end

get '/' do
  print "Redirecting...\n"
  call(env.merge("PATH_INFO" => '/nodes'))
end


get '*' do
  print params[:splat]
  print "2Redirecting...\n"
  call(env.merge("PATH_INFO" => '/nodes'))
end
